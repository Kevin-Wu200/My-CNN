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
    def process_tiles_parallel(
        tiles: List[Any],
        process_func: Callable,
        num_workers: Optional[int] = None,
        max_workers: int = MAX_WORKERS_LIMIT,
        error_handling: str = "log",
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

        Returns:
            (处理是否成功, 处理结果列表, 错误信息列表, 消息)
        """
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

            # 使用进程池处理
            with Pool(processes=num_workers) as pool:
                for tile_idx, tile in enumerate(tiles):
                    try:
                        result = pool.apply_async(process_func, tile)
                        results.append((tile_idx, result))
                        logger.debug(f"分块 {tile_idx} 已提交到工作进程池")
                    except Exception as e:
                        error_info = {
                            "tile_index": tile_idx,
                            "error": str(e),
                        }
                        errors.append(error_info)
                        logger.error(
                            f"分块 {tile_idx} 提交失败: {str(e)}"
                        )

                        if error_handling == "stop":
                            return False, None, errors, f"分块处理中断: {str(e)}"

                # 收集结果
                processed_results = []
                for result_idx, (tile_idx, result) in enumerate(results):
                    try:
                        # 增加超时机制，防止工作进程崩溃导致无限阻塞
                        tile_result = result.get(timeout=RESULT_TIMEOUT)
                        processed_results.append(tile_result)
                        logger.debug(f"分块 {tile_idx} 处理完成")
                    except mp.TimeoutError:
                        error_info = {
                            "tile_index": tile_idx,
                            "result_index": result_idx,
                            "error": f"分块处理超时（>{RESULT_TIMEOUT}秒），可能是工作进程崩溃或卡死",
                        }
                        errors.append(error_info)
                        logger.error(
                            f"分块 {tile_idx} 处理超时（>{RESULT_TIMEOUT}秒）"
                        )

                        if error_handling == "stop":
                            return False, None, errors, f"分块处理中断: 超时"

                        processed_results.append(None)
                    except Exception as e:
                        error_info = {
                            "tile_index": tile_idx,
                            "result_index": result_idx,
                            "error": str(e),
                        }
                        errors.append(error_info)
                        logger.error(
                            f"分块 {tile_idx} 处理失败: {str(e)}"
                        )

                        if error_handling == "stop":
                            return False, None, errors, f"分块处理中断: {str(e)}"

                        processed_results.append(None)

            logger.info(
                f"并行处理完成: {len(processed_results)} 个结果, "
                f"{len(errors)} 个错误"
            )

            success = len(errors) == 0
            message = "并行处理成功" if success else f"并行处理完成，{len(errors)} 个分块出错"

            return success, processed_results, errors, message

        except Exception as e:
            logger.error(f"并行处理失败: {str(e)}")
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

            # 使用进程池处理
            with Pool(processes=num_workers) as pool:
                results = pool.map(process_func, chunk_data_list)

            logger.info(f"并行处理完成: {len(results)} 个结果")

            return True, results, "并行处理成功"

        except Exception as e:
            logger.error(f"并行处理失败: {str(e)}")
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
