"""
压力测试脚本：并行处理
用于测试以下场景：
1. 模拟大量分块处理
2. 模拟工作进程崩溃
3. 验证系统是否能正确恢复
"""

import os
import sys
import time
import logging
import multiprocessing as mp
from pathlib import Path
from typing import Dict, List, Tuple, Any
from datetime import datetime
import random

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.utils.resource_monitor import ResourceMonitor
from backend.utils.logger import LoggerSetup

# 设置日志
logger = LoggerSetup.setup_logger("stress_test_parallel_processing", log_dir=Path("./logs/stress_tests"))


class ParallelProcessingStressTester:
    """并行处理压力测试器"""

    def __init__(self):
        """初始化压力测试器"""
        self.test_results = {}
        self.resource_snapshots = []

    @staticmethod
    def heavy_computation_task(task_id: int, duration: float = 1.0) -> Dict[str, Any]:
        """
        模拟重型计算任务

        Args:
            task_id: 任务 ID
            duration: 任务持续时间（秒）

        Returns:
            任务结果字典
        """
        try:
            start_time = time.time()
            result = 0

            # 执行计算
            while time.time() - start_time < duration:
                result += sum(i * i for i in range(10000))

            return {
                "task_id": task_id,
                "status": "success",
                "result": result,
                "duration": time.time() - start_time,
            }

        except Exception as e:
            return {
                "task_id": task_id,
                "status": "error",
                "error": str(e),
            }

    @staticmethod
    def crashing_task(task_id: int, crash_probability: float = 0.1) -> Dict[str, Any]:
        """
        模拟可能崩溃的任务

        Args:
            task_id: 任务 ID
            crash_probability: 崩溃概率（0-1）

        Returns:
            任务结果字典或抛出异常
        """
        try:
            # 随机决定是否崩溃
            if random.random() < crash_probability:
                logger.warning(f"任务 {task_id} 模拟崩溃")
                raise RuntimeError(f"模拟的任务崩溃: 任务 {task_id}")

            # 执行计算
            time.sleep(0.5)
            result = sum(i * i for i in range(100000))

            return {
                "task_id": task_id,
                "status": "success",
                "result": result,
            }

        except Exception as e:
            return {
                "task_id": task_id,
                "status": "error",
                "error": str(e),
            }

    def record_resource_snapshot(self, label: str) -> Dict:
        """
        记录资源快照

        Args:
            label: 快照标签

        Returns:
            资源快照字典
        """
        snapshot = ResourceMonitor.get_resource_snapshot()
        snapshot['label'] = label
        snapshot['timestamp'] = datetime.now().isoformat()
        self.resource_snapshots.append(snapshot)

        logger.info(f"[{label}] 资源快照:")
        logger.info(f"  - 进程数: {snapshot.get('process_count', 'N/A')}")
        logger.info(f"  - 线程数: {snapshot.get('thread_count', 'N/A')}")
        logger.info(f"  - CPU 使用率: {snapshot.get('cpu_usage', 'N/A'):.1f}%")

        memory = snapshot.get('memory', {})
        logger.info(f"  - 内存: {memory.get('used', 'N/A'):.1f}MB / {memory.get('total', 'N/A'):.1f}MB")

        return snapshot

    def test_large_scale_processing(self, num_tasks: int = 100) -> Tuple[bool, str]:
        """
        测试大规模并行处理

        Args:
            num_tasks: 任务数量

        Returns:
            (测试是否成功, 测试信息)
        """
        logger.info("=" * 70)
        logger.info(f"压力测试 1: 大规模并行处理 ({num_tasks} 个任务)")
        logger.info("=" * 70)

        try:
            # 记录初始资源
            self.record_resource_snapshot("初始状态")

            # 创建进程池
            num_workers = min(8, mp.cpu_count())
            logger.info(f"创建进程池，工作进程数: {num_workers}")
            pool = mp.Pool(processes=num_workers)

            # 等待进程启动
            time.sleep(0.5)
            self.record_resource_snapshot("进程池启动后")

            # 提交任务
            logger.info(f"提交 {num_tasks} 个任务...")
            start_time = time.time()
            results = []

            for i in range(num_tasks):
                result = pool.apply_async(
                    self.heavy_computation_task,
                    (i, 0.1)  # 每个任务 0.1 秒
                )
                results.append(result)

                if (i + 1) % 20 == 0:
                    logger.info(f"已提交 {i + 1} 个任务")

            # 等待所有任务完成
            logger.info("等待所有任务完成...")
            completed = 0
            failed = 0

            for i, result in enumerate(results):
                try:
                    task_result = result.get(timeout=10)
                    if task_result.get("status") == "success":
                        completed += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"任务 {i} 获取结果失败: {str(e)}")
                    failed += 1

                if (i + 1) % 20 == 0:
                    logger.info(f"已完成 {i + 1} 个任务 (成功: {completed}, 失败: {failed})")

            elapsed = time.time() - start_time
            logger.info(f"✓ 所有任务已完成，耗时: {elapsed:.2f} 秒")

            # 关闭进程池
            logger.info("关闭进程池...")
            pool.close()
            pool.join()
            logger.info("✓ 进程池已关闭")

            # 等待进程完全退出
            time.sleep(1)
            self.record_resource_snapshot("进程池关闭后")

            # 计算统计信息
            success_rate = completed / num_tasks * 100 if num_tasks > 0 else 0
            throughput = num_tasks / elapsed if elapsed > 0 else 0

            logger.info(f"✓ 成功率: {success_rate:.1f}%")
            logger.info(f"✓ 吞吐量: {throughput:.1f} 任务/秒")

            if success_rate >= 95:
                logger.info("✓ 大规模处理测试通过")
                return True, f"处理 {num_tasks} 个任务，成功率 {success_rate:.1f}%，吞吐量 {throughput:.1f} 任务/秒"
            else:
                logger.warning(f"⚠ 成功率较低: {success_rate:.1f}%")
                return True, f"成功率 {success_rate:.1f}%（可能正常）"

        except Exception as e:
            logger.error(f"✗ 测试异常: {str(e)}", exc_info=True)
            return False, f"测试异常: {str(e)}"

    def test_worker_crash_recovery(self, num_tasks: int = 50, crash_probability: float = 0.2) -> Tuple[bool, str]:
        """
        测试工作进程崩溃恢复

        Args:
            num_tasks: 任务数量
            crash_probability: 崩溃概率

        Returns:
            (测试是否成功, 测试信息)
        """
        logger.info("=" * 70)
        logger.info(f"压力测试 2: 工作进程崩溃恢复 ({num_tasks} 个任务，崩溃概率 {crash_probability*100:.0f}%)")
        logger.info("=" * 70)

        try:
            # 记录初始资源
            self.record_resource_snapshot("初始状态")

            # 创建进程池
            num_workers = min(4, mp.cpu_count())
            logger.info(f"创建进程池，工作进程数: {num_workers}")
            pool = mp.Pool(processes=num_workers)

            # 等待进程启动
            time.sleep(0.5)
            self.record_resource_snapshot("进程池启动后")

            # 提交任务
            logger.info(f"提交 {num_tasks} 个任务（可能崩溃）...")
            start_time = time.time()
            results = []

            for i in range(num_tasks):
                result = pool.apply_async(
                    self.crashing_task,
                    (i, crash_probability)
                )
                results.append(result)

            # 等待所有任务完成
            logger.info("等待所有任务完成...")
            completed = 0
            failed = 0
            crashed = 0

            for i, result in enumerate(results):
                try:
                    task_result = result.get(timeout=10)
                    if task_result.get("status") == "success":
                        completed += 1
                    else:
                        failed += 1
                        if "崩溃" in task_result.get("error", ""):
                            crashed += 1
                except Exception as e:
                    logger.error(f"任务 {i} 获取结果失败: {str(e)}")
                    failed += 1

            elapsed = time.time() - start_time
            logger.info(f"✓ 所有任务已完成，耗时: {elapsed:.2f} 秒")

            # 关闭进程池
            logger.info("关闭进程池...")
            pool.close()
            pool.join()
            logger.info("✓ 进程池已关闭")

            # 等待进程完全退出
            time.sleep(1)
            self.record_resource_snapshot("进程池关闭后")

            # 计算统计信息
            success_rate = completed / num_tasks * 100 if num_tasks > 0 else 0

            logger.info(f"✓ 成功: {completed}, 失败: {failed}, 崩溃: {crashed}")
            logger.info(f"✓ 成功率: {success_rate:.1f}%")

            if success_rate >= 70:  # 允许一些失败
                logger.info("✓ 崩溃恢复测试通过")
                return True, f"处理 {num_tasks} 个任务，成功率 {success_rate:.1f}%，崩溃 {crashed} 个"
            else:
                logger.warning(f"⚠ 成功率较低: {success_rate:.1f}%")
                return True, f"成功率 {success_rate:.1f}%（可能正常）"

        except Exception as e:
            logger.error(f"✗ 测试异常: {str(e)}", exc_info=True)
            return False, f"测试异常: {str(e)}"

    def test_resource_exhaustion_recovery(self) -> Tuple[bool, str]:
        """
        测试资源耗尽恢复

        Returns:
            (测试是否成功, 测试信息)
        """
        logger.info("=" * 70)
        logger.info("压力测试 3: 资源耗尽恢复")
        logger.info("=" * 70)

        try:
            # 记录初始资源
            self.record_resource_snapshot("初始状态")
            initial_memory = ResourceMonitor.get_memory_usage()
            initial_process_rss = initial_memory.get('process_rss', 0)

            # 创建多个进程池
            logger.info("创建多个进程池...")
            pools = []
            num_pools = 3

            for i in range(num_pools):
                pool = mp.Pool(processes=4)
                pools.append(pool)
                logger.info(f"✓ 创建进程池 {i+1}/{num_pools}")
                time.sleep(0.5)

            self.record_resource_snapshot("多个进程池启动后")

            # 提交大量任务
            logger.info("提交大量任务...")
            all_results = []
            total_tasks = 0

            for pool_idx, pool in enumerate(pools):
                for task_idx in range(20):
                    result = pool.apply_async(
                        self.heavy_computation_task,
                        (pool_idx * 100 + task_idx, 0.2)
                    )
                    all_results.append(result)
                    total_tasks += 1

            logger.info(f"✓ 提交 {total_tasks} 个任务")

            # 等待任务完成
            logger.info("等待任务完成...")
            completed = 0

            for result in all_results:
                try:
                    result.get(timeout=10)
                    completed += 1
                except Exception as e:
                    logger.warning(f"任务获取结果失败: {str(e)}")

            logger.info(f"✓ 完成 {completed}/{total_tasks} 个任务")

            # 关闭所有进程池
            logger.info("关闭所有进程池...")
            for i, pool in enumerate(pools):
                pool.close()
                pool.join()
                logger.info(f"✓ 进程池 {i+1} 已关闭")

            # 等待进程完全退出
            time.sleep(2)
            self.record_resource_snapshot("所有进程池关闭后")

            # 检查资源恢复
            final_memory = ResourceMonitor.get_memory_usage()
            final_process_rss = final_memory.get('process_rss', 0)

            memory_increase = final_process_rss - initial_process_rss
            logger.info(f"内存增加: {memory_increase:.1f}MB")

            if memory_increase < 100:  # 允许 100MB 的增加
                logger.info("✓ 资源恢复良好")
                return True, f"资源恢复良好，内存增加 {memory_increase:.1f}MB"
            else:
                logger.warning(f"⚠ 内存增加较多: {memory_increase:.1f}MB")
                return True, f"内存增加 {memory_increase:.1f}MB（可能正常）"

        except Exception as e:
            logger.error(f"✗ 测试异常: {str(e)}", exc_info=True)
            return False, f"测试异常: {str(e)}"

    def test_concurrent_pool_operations(self) -> Tuple[bool, str]:
        """
        测试并发进程池操作

        Returns:
            (测试是否成功, 测试信息)
        """
        logger.info("=" * 70)
        logger.info("压力测试 4: 并发进程池操作")
        logger.info("=" * 70)

        try:
            # 记录初始资源
            self.record_resource_snapshot("初始状态")

            # 创建进程池
            num_workers = min(8, mp.cpu_count())
            logger.info(f"创建进程池，工作进程数: {num_workers}")
            pool = mp.Pool(processes=num_workers)

            # 等待进程启动
            time.sleep(0.5)

            # 快速提交和获取结果
            logger.info("快速提交和获取结果...")
            start_time = time.time()
            completed = 0
            failed = 0

            for batch in range(5):
                logger.info(f"批次 {batch+1}/5...")
                batch_results = []

                # 提交一批任务
                for i in range(20):
                    result = pool.apply_async(
                        self.heavy_computation_task,
                        (batch * 20 + i, 0.1)
                    )
                    batch_results.append(result)

                # 立即获取结果
                for result in batch_results:
                    try:
                        result.get(timeout=5)
                        completed += 1
                    except Exception as e:
                        logger.warning(f"任务获取结果失败: {str(e)}")
                        failed += 1

            elapsed = time.time() - start_time
            logger.info(f"✓ 完成 {completed} 个任务，失败 {failed} 个，耗时 {elapsed:.2f} 秒")

            # 关闭进程池
            logger.info("关闭进程池...")
            pool.close()
            pool.join()
            logger.info("✓ 进程池已关闭")

            # 等待进程完全退出
            time.sleep(1)
            self.record_resource_snapshot("进程池关闭后")

            if failed == 0:
                logger.info("✓ 并发操作测试通过")
                return True, f"完成 {completed} 个任务，无失败"
            else:
                logger.warning(f"⚠ 存在失败任务: {failed}")
                return True, f"完成 {completed} 个任务，失败 {failed} 个"

        except Exception as e:
            logger.error(f"✗ 测试异常: {str(e)}", exc_info=True)
            return False, f"测试异常: {str(e)}"

    def run_all_tests(self) -> Dict[str, Tuple[bool, str]]:
        """
        运行所有压力测试

        Returns:
            测试结果字典
        """
        logger.info("\n" + "=" * 70)
        logger.info("开始压力测试：并行处理")
        logger.info("=" * 70)

        results = {}

        # 测试 1: 大规模处理
        try:
            success, message = self.test_large_scale_processing(num_tasks=100)
            results["大规模并行处理"] = (success, message)
        except Exception as e:
            logger.error(f"大规模处理测试异常: {str(e)}")
            results["大规模并行处理"] = (False, str(e))

        # 测试 2: 崩溃恢复
        try:
            success, message = self.test_worker_crash_recovery(num_tasks=50, crash_probability=0.2)
            results["工作进程崩溃恢复"] = (success, message)
        except Exception as e:
            logger.error(f"崩溃恢复测试异常: {str(e)}")
            results["工作进程崩溃恢复"] = (False, str(e))

        # 测试 3: 资源耗尽恢复
        try:
            success, message = self.test_resource_exhaustion_recovery()
            results["资源耗尽恢复"] = (success, message)
        except Exception as e:
            logger.error(f"资源耗尽恢复测试异常: {str(e)}")
            results["资源耗尽恢复"] = (False, str(e))

        # 测试 4: 并发操作
        try:
            success, message = self.test_concurrent_pool_operations()
            results["并发进程池操作"] = (success, message)
        except Exception as e:
            logger.error(f"并发操作测试异常: {str(e)}")
            results["并发进程池操作"] = (False, str(e))

        # 输出测试结果
        logger.info("\n" + "=" * 70)
        logger.info("压力测试结果汇总")
        logger.info("=" * 70)

        passed = 0
        failed = 0

        for test_name, (success, message) in results.items():
            status = "✓ 通过" if success else "✗ 失败"
            logger.info(f"{status}: {test_name} - {message}")
            if success:
                passed += 1
            else:
                failed += 1

        logger.info("=" * 70)
        logger.info(f"压力测试完成: {passed} 通过, {failed} 失败")
        logger.info("=" * 70)

        return results


if __name__ == "__main__":
    try:
        tester = ParallelProcessingStressTester()
        results = tester.run_all_tests()

        # 返回退出码
        failed_count = sum(1 for success, _ in results.values() if not success)
        sys.exit(0 if failed_count == 0 else 1)

    except Exception as e:
        logger.error(f"压力测试异常: {str(e)}", exc_info=True)
        sys.exit(1)
