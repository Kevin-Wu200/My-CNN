"""
并行处理服务模块
用于并行处理多个影像块
自动根据设备 CPU 核心数确定并行处理数量
"""

import multiprocessing as mp
from multiprocessing import Pool, Manager
from pathlib import Path
from typing import Tuple, Optional, List, Callable, Dict, Any
import logging
import time
import os
import signal

from backend.utils.resource_monitor import ResourceMonitor

logger = logging.getLogger(__name__)

# 系统配置
MAX_WORKERS_LIMIT = 16  # 最大工作进程数上限
MIN_WORKERS = 1  # 最小工作进程数
DEFAULT_PARALLEL_WORKERS = 8  # 默认并行处理数量


class ParallelProcessingService:
    """并行处理服务类"""

    @staticmethod
    def get_auto_worker_count(max_limit: int = MAX_WORKERS_LIMIT) -> int:
        """
        自动获取工作进程数

        系统优先使用默认的 8 个工作进程进行并行处理。
        如果 CPU 核心数不足，则根据以下规则调整：
        - 使用 CPU 核心数的 1/2（向下取整）
        - 不超过 max_limit 上限

        Args:
            max_limit: 最大工作进程数上限（默认 16）

        Returns:
            自动计算的工作进程数
        """
        cpu_count = mp.cpu_count()
        # 优先使用默认的 8 个工作进程
        num_workers = min(DEFAULT_PARALLEL_WORKERS, cpu_count, max_limit)
        # 确保至少有 1 个工作进程
        num_workers = max(num_workers, MIN_WORKERS)

        logger.info(
            f"自动检测工作进程数: CPU 核心数={cpu_count}, "
            f"使用工作进程数={num_workers}（默认并行处理数={DEFAULT_PARALLEL_WORKERS}）"
        )

        return num_workers

    @staticmethod
    def _cleanup_pool(pool: Pool, force: bool = False) -> None:
        """
        清理进程池资源

        Args:
            pool: 进程池对象
            force: 是否强制终止所有工作进程
        """
        try:
            if force:
                logger.warning("强制终止所有工作进程...")
                pool.terminate()
                logger.info("已发送终止信号到所有工作进程")
            else:
                logger.debug("正常关闭进程池，等待所有工作进程完成...")
                pool.close()

            # 显式等待所有进程完全退出
            logger.debug("等待所有工作进程完全退出...")
            pool.join()
            logger.info("所有工作进程已完全退出")

        except Exception as e:
            logger.error(f"进程池清理过程中出错: {str(e)}")

    @staticmethod
    def _force_terminate_workers(pool: Pool, timeout: int = 5) -> None:
        """
        强制终止工作进程

        Args:
            pool: 进程池对象
            timeout: 等待超时时间（秒）
        """
        try:
            logger.warning(f"尝试强制终止工作进程（超时时间: {timeout}秒）...")
            pool.terminate()
            start_time = time.time()

            # 等待进程完全退出
            while time.time() - start_time < timeout:
                if not any(p.is_alive() for p in pool._pool):
                    logger.info("所有工作进程已成功终止")
                    return
                time.sleep(0.1)

            logger.warning(f"在 {timeout} 秒内未能完全终止所有工作进程")

        except Exception as e:
            logger.error(f"强制终止工作进程时出错: {str(e)}")

    @staticmethod
    def process_tiles_parallel(
        tiles: List[Any],
        process_func: Callable,
        num_workers: Optional[int] = None,
        max_workers: int = MAX_WORKERS_LIMIT,
        error_handling: str = "log",
        task_manager=None,
        task_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[List[Any]], List[Dict], str]:
        """
        并行处理多个影像分块

        每个分块作为一个独立任务提交至并行池处理。
        系统自动根据 CPU 核心数确定工作进程数，用户无需手动指定。

        Args:
            tiles: Tile 对象列表（来自 TilingService）
            process_func: 处理函数，接收单个 Tile 对象，返回处理结果
            num_workers: 工作进程数（如果为 None，则自动检测）
            max_workers: 最大工作进程数上限
            error_handling: 错误处理方式
                - "log": 记录错误但继续处理其他分块
                - "stop": 遇到错误立即停止
            task_manager: 任务管理器（用于进程注册和停止标志检查）
            task_id: 任务ID（用于进度跟踪）

        Returns:
            (处理是否成功, 处理结果列表, 错误信息列表, 消息)
        """
        pool = None
        try:
            if not tiles or len(tiles) == 0:
                return False, None, [], "分块列表为空"

            # 自动确定工作进程数
            if num_workers is None:
                num_workers = ParallelProcessingService.get_auto_worker_count(
                    max_limit=max_workers
                )
            else:
                # 验证用户指定的工作进程数
                if num_workers <= 0:
                    return False, None, [], "工作进程数必须为正数"
                num_workers = min(num_workers, max_workers)

            logger.info(
                f"开始并行处理分块: {len(tiles)} 个分块, "
                f"{num_workers} 个工作进程"
            )

            results = []
            errors = []
            RESULT_TIMEOUT = 300  # 5分钟超时

            # 创建进程池并记录生命周期
            pool = Pool(processes=num_workers)
            logger.info(
                f"进程池已创建: {num_workers} 个工作进程, "
                f"进程池ID: {id(pool)}"
            )

            # 第五步：注册进程池到任务管理器
            if task_manager and task_id:
                task_manager.register_process(task_id, pool)
                logger.info(f"[{task_id}] 进程池已注册到任务管理器")

            try:
                # 提交所有分块任务
                for tile_idx, tile in enumerate(tiles):
                    # 检查停止标志
                    if task_manager and task_manager.is_stop_requested(task_id):
                        logger.info(f"[{task_id}] 检测任务被停止（分块提交中，已提交 {tile_idx}/{len(tiles)} 个分块）")
                        ParallelProcessingService._cleanup_pool(pool, force=True)
                        return False, None, [], "检测任务被用户停止"

                    try:
                        # 修复：使用 args=(tile,) 而不是直接传递 tile
                        # pool.apply_async(func, args) 会将 args 中的元素作为函数的参数
                        # 如果 tile 是一个元组 (service, tile_obj, n_clusters, min_area, nodata_value)
                        # 直接传递会被解包为 5 个参数，但函数只期望 1 个参数
                        # 使用 args=(tile,) 会将整个元组作为单个参数传递
                        result = pool.apply_async(process_func, args=(tile,))
                        results.append((tile_idx, result))
                        logger.debug(
                            f"分块 {tile_idx} 已提交到工作进程池 "
                            f"(总进度: {tile_idx + 1}/{len(tiles)})"
                        )
                        # 每提交10个分块记录一次资源状态
                        if (tile_idx + 1) % 10 == 0:
                            ResourceMonitor.log_resource_status(f"分块提交进度 ({tile_idx + 1}/{len(tiles)})")
                    except Exception as e:
                        error_info = {
                            "tile_index": tile_idx,
                            "error": str(e),
                            "stage": "submission",
                        }
                        errors.append(error_info)
                        logger.error(
                            f"分块 {tile_idx} 提交失败: {str(e)}"
                        )

                        if error_handling == "stop":
                            logger.warning("错误处理模式为 'stop'，中断处理")
                            ParallelProcessingService._cleanup_pool(pool, force=True)
                            return False, None, errors, f"分块处理中断: {str(e)}"

                # 收集结果
                processed_results = []
                logger.info(f"开始收集 {len(results)} 个分块的处理结果...")
                ResourceMonitor.log_resource_status("开始收集分块处理结果")

                for result_idx, (tile_idx, result) in enumerate(results):
                    # 检查停止标志
                    if task_manager and task_manager.is_stop_requested(task_id):
                        logger.info(f"[{task_id}] 检测任务被停止（结果收集中，已收集 {result_idx}/{len(results)} 个结果）")
                        ParallelProcessingService._cleanup_pool(pool, force=True)
                        return False, None, [], "检测任务被用户停止"

                    try:
                        logger.debug(
                            f"等待分块 {tile_idx} 的处理结果 "
                            f"(进度: {result_idx + 1}/{len(results)}, 超时: {RESULT_TIMEOUT}秒)"
                        )

                        # 增加超时机制，防止工作进程崩溃导致无限阻塞
                        tile_result = result.get(timeout=RESULT_TIMEOUT)
                        processed_results.append(tile_result)
                        logger.info(
                            f"分块 {tile_idx} 处理完成 "
                            f"(进度: {result_idx + 1}/{len(results)})"
                        )
                        # 每完成10个分块记录一次资源状态
                        if (result_idx + 1) % 10 == 0:
                            ResourceMonitor.log_resource_status(f"分块完成进度 ({result_idx + 1}/{len(results)})")

                    except mp.TimeoutError:
                        error_info = {
                            "tile_index": tile_idx,
                            "result_index": result_idx,
                            "error": f"分块处理超时（>{RESULT_TIMEOUT}秒），可能是工作进程崩溃或卡死",
                            "stage": "result_collection",
                        }
                        errors.append(error_info)
                        logger.error(
                            f"分块 {tile_idx} 处理超时（>{RESULT_TIMEOUT}秒）, "
                            f"可能是工作进程崩溃或卡死"
                        )

                        # 超时时强制终止工作进程
                        logger.warning(
                            f"分块 {tile_idx} 超时，尝试强制终止工作进程..."
                        )
                        ParallelProcessingService._force_terminate_workers(pool, timeout=5)

                        if error_handling == "stop":
                            logger.warning("错误处理模式为 'stop'，中断处理")
                            ParallelProcessingService._cleanup_pool(pool, force=True)
                            return False, None, errors, f"分块处理中断: 超时"

                        processed_results.append(None)

                    except Exception as e:
                        error_info = {
                            "tile_index": tile_idx,
                            "result_index": result_idx,
                            "error": str(e),
                            "stage": "result_collection",
                        }
                        errors.append(error_info)
                        logger.error(
                            f"分块 {tile_idx} 处理失败: {str(e)}"
                        )

                        if error_handling == "stop":
                            logger.warning("错误处理模式为 'stop'，中断处理")
                            ParallelProcessingService._cleanup_pool(pool, force=True)
                            return False, None, errors, f"分块处理中断: {str(e)}"

                        processed_results.append(None)

                logger.info(
                    f"所有分块处理结果已收集: {len(processed_results)} 个结果, "
                    f"{len(errors)} 个错误"
                )

            finally:
                # 确保进程池被正确清理
                logger.info(f"开始清理进程池 (ID: {id(pool)})...")
                ResourceMonitor.log_resource_status(f"清理进程池前 (ID: {id(pool)})")
                ParallelProcessingService._cleanup_pool(pool, force=False)
                logger.info(f"进程池已清理 (ID: {id(pool)})")
                ResourceMonitor.log_resource_status(f"清理进程池后 (ID: {id(pool)})")

                # 清理进程注册
                if task_manager and task_id and task_id in task_manager.active_processes:
                    del task_manager.active_processes[task_id]
                    logger.info(f"[{task_id}] 进程注册已清理")

            logger.info(
                f"并行处理完成: {len(processed_results)} 个结果, "
                f"{len(errors)} 个错误"
            )

            success = len(errors) == 0
            message = "并行处理成功" if success else f"并行处理完成，{len(errors)} 个分块出错"

            return success, processed_results, errors, message

        except Exception as e:
            logger.error(f"并行处理失败: {str(e)}")

            # 异常时强制清理进程池
            if pool is not None:
                logger.warning("异常发生，强制清理进程池...")
                try:
                    ParallelProcessingService._cleanup_pool(pool, force=True)
                except Exception as cleanup_error:
                    logger.error(f"异常清理进程池时出错: {str(cleanup_error)}")

            return False, None, [], f"并行处理失败: {str(e)}"

    @staticmethod
    def process_chunks_parallel(
        chunk_data_list: List[Dict[str, Any]],
        process_func: Callable,
        num_workers: Optional[int] = None,
        max_workers: int = MAX_WORKERS_LIMIT,
    ) -> Tuple[bool, Optional[List[Any]], str]:
        """
        并行处理多个影像块（兼容旧接口）

        Args:
            chunk_data_list: 块数据列表
            process_func: 处理函数
            num_workers: 工作进程数（如果为 None，则自动检测）
            max_workers: 最大工作进程数上限

        Returns:
            (处理是否成功, 处理结果列表, 错误信息或成功消息)
        """
        pool = None
        try:
            if not chunk_data_list:
                return False, None, "块数据列表为空"

            # 自动确定工作进程数
            if num_workers is None:
                num_workers = ParallelProcessingService.get_auto_worker_count(
                    max_limit=max_workers
                )
            else:
                if num_workers <= 0:
                    return False, None, "工作进程数必须为正数"
                num_workers = min(num_workers, max_workers)

            logger.info(
                f"开始并行处理: {len(chunk_data_list)} 个块, "
                f"{num_workers} 个工作进程"
            )

            # 创建进程池并记录生命周期
            pool = Pool(processes=num_workers)
            logger.info(
                f"进程池已创建: {num_workers} 个工作进程, "
                f"进程池ID: {id(pool)}"
            )
            ResourceMonitor.log_resource_status(f"进程池创建后 (ID: {id(pool)})")

            try:
                # 使用进程池处理
                logger.debug(f"提交 {len(chunk_data_list)} 个块到进程池...")
                # 使用 map 而不是 starmap
                # chunk_data_list 中的每个元素都是一个元组 (service, tile, n_clusters, min_area, nodata_value)
                # pool.map() 会将每个元组作为单个参数传递给函数
                results = pool.map(process_func, chunk_data_list)
                logger.info(f"所有块已处理: {len(results)} 个结果")

            finally:
                # 确保进程池被正确清理
                logger.info(f"开始清理进程池 (ID: {id(pool)})...")
                ResourceMonitor.log_resource_status(f"清理进程池前 (ID: {id(pool)})")
                ParallelProcessingService._cleanup_pool(pool, force=False)
                logger.info(f"进程池已清理 (ID: {id(pool)})")
                ResourceMonitor.log_resource_status(f"清理进程池后 (ID: {id(pool)})")

            logger.info(f"并行处理完成: {len(results)} 个结果")

            return True, results, "并行处理成功"

        except Exception as e:
            logger.error(f"并行处理失败: {str(e)}")

            # 异常时强制清理进程池
            if pool is not None:
                logger.warning("异常发生，强制清理进程池...")
                try:
                    ParallelProcessingService._cleanup_pool(pool, force=True)
                except Exception as cleanup_error:
                    logger.error(f"异常清理进程池时出错: {str(cleanup_error)}")

            return False, None, f"并行处理失败: {str(e)}"

    @staticmethod
    def validate_parallel_parameters(
        num_workers: Optional[int] = None,
        max_workers: int = MAX_WORKERS_LIMIT,
    ) -> Tuple[bool, str]:
        """
        验证并行处理参数

        Args:
            num_workers: 工作进程数（如果为 None，则使用自动检测值）
            max_workers: 最大工作进程数

        Returns:
            (验证是否通过, 错误信息或成功消息)
        """
        cpu_count = mp.cpu_count()

        if num_workers is None:
            # 自动检测
            auto_workers = ParallelProcessingService.get_auto_worker_count(
                max_limit=max_workers
            )
            return True, f"并行参数验证通过 (自动检测: {auto_workers} 个工作进程)"

        if num_workers <= 0:
            return False, "工作进程数必须为正数"

        if num_workers > max_workers:
            return False, f"工作进程数不能超过 {max_workers}"

        return True, "并行参数验证通过"
