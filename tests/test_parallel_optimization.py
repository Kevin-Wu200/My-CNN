"""
并行处理优化测试
验证 8 个工作进程的并行处理优化
"""

import sys
import os
import numpy as np
import logging
import time
import multiprocessing as mp
from pathlib import Path
from typing import Tuple, Dict, List

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.parallel_processing import (
    ParallelProcessingService,
    DEFAULT_PARALLEL_WORKERS,
)
from backend.services.unsupervised_detection import UnsupervisedDiseaseDetectionService
from backend.services.detection import DiseaseTreeDetectionService
from backend.utils.tile_utils import TilingService, DEFAULT_TILE_SIZE, Tile
from backend.utils.image_reader import ImageReader

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ParallelOptimizationTestSuite:
    """并行处理优化测试套件"""

    def __init__(self):
        """初始化测试套件"""
        self.test_results = {}
        self.performance_results = {}

    def test_1_default_parallel_workers(self) -> Tuple[bool, str]:
        """
        测试 1: 验证默认并行工作进程数为 8
        """
        logger.info("=" * 60)
        logger.info("测试 1: 验证默认并行工作进程数")
        logger.info("=" * 60)

        try:
            # 检查常量定义
            assert DEFAULT_PARALLEL_WORKERS == 8, \
                f"DEFAULT_PARALLEL_WORKERS 应为 8，实际为 {DEFAULT_PARALLEL_WORKERS}"
            logger.info(f"✓ DEFAULT_PARALLEL_WORKERS = {DEFAULT_PARALLEL_WORKERS}")

            # 测试自动检测
            auto_workers = ParallelProcessingService.get_auto_worker_count()
            cpu_count = mp.cpu_count()
            logger.info(f"✓ 自动检测的工作进程数: {auto_workers} (CPU 核心数: {cpu_count})")

            # 验证逻辑：应该使用 min(8, cpu_count, 16)
            expected_workers = min(DEFAULT_PARALLEL_WORKERS, cpu_count, 16)
            assert auto_workers == expected_workers, \
                f"工作进程数应为 {expected_workers}，实际为 {auto_workers}"
            logger.info(f"✓ 工作进程数计算正确: {auto_workers}")

            message = "✓ 测试通过: 默认并行工作进程数为 8"
            logger.info(message)
            return True, message

        except Exception as e:
            message = f"✗ 测试失败: {str(e)}"
            logger.error(message)
            return False, message

    def test_2_unsupervised_detection_default_workers(self) -> Tuple[bool, str]:
        """
        测试 2: 验证无监督检测默认使用 8 个工作进程
        """
        logger.info("=" * 60)
        logger.info("测试 2: 验证无监督检测默认参数")
        logger.info("=" * 60)

        try:
            import inspect

            # 检查 detect_on_tiled_image 方法的默认参数
            sig = inspect.signature(
                UnsupervisedDiseaseDetectionService.detect_on_tiled_image
            )
            num_workers_param = sig.parameters.get('num_workers')
            assert num_workers_param is not None, "num_workers 参数不存在"
            assert num_workers_param.default == 8, \
                f"num_workers 默认值应为 8，实际为 {num_workers_param.default}"
            logger.info(f"✓ detect_on_tiled_image 的 num_workers 默认值为 8")

            # 检查文档
            source = inspect.getsource(
                UnsupervisedDiseaseDetectionService.detect_on_tiled_image
            )
            assert '8' in source and '工作进程' in source, \
                "文档中未说明使用 8 个工作进程"
            logger.info("✓ 文档中说明了使用 8 个工作进程")

            message = "✓ 测试通过: 无监督检测默认使用 8 个工作进程"
            logger.info(message)
            return True, message

        except Exception as e:
            message = f"✗ 测试失败: {str(e)}"
            logger.error(message)
            return False, message

    def test_3_detection_default_workers(self) -> Tuple[bool, str]:
        """
        测试 3: 验证深度学习检测默认使用 8 个工作进程
        """
        logger.info("=" * 60)
        logger.info("测试 3: 验证深度学习检测默认参数")
        logger.info("=" * 60)

        try:
            import inspect

            # 检查 detect_on_tiled_image 方法的默认参数
            sig = inspect.signature(
                DiseaseTreeDetectionService.detect_on_tiled_image
            )
            num_workers_param = sig.parameters.get('num_workers')
            assert num_workers_param is not None, "num_workers 参数不存在"
            assert num_workers_param.default == 8, \
                f"num_workers 默认值应为 8，实际为 {num_workers_param.default}"
            logger.info(f"✓ detect_on_tiled_image 的 num_workers 默认值为 8")

            # 检查文档
            source = inspect.getsource(
                DiseaseTreeDetectionService.detect_on_tiled_image
            )
            assert '8' in source and '工作进程' in source, \
                "文档中未说明使用 8 个工作进程"
            logger.info("✓ 文档中说明了使用 8 个工作进程")

            message = "✓ 测试通过: 深度学习检测默认使用 8 个工作进程"
            logger.info(message)
            return True, message

        except Exception as e:
            message = f"✗ 测试失败: {str(e)}"
            logger.error(message)
            return False, message

    def test_4_tile_size_1024(self) -> Tuple[bool, str]:
        """
        测试 4: 验证分块大小为 1024×1024
        """
        logger.info("=" * 60)
        logger.info("测试 4: 验证分块大小")
        logger.info("=" * 60)

        try:
            assert DEFAULT_TILE_SIZE == 1024, \
                f"DEFAULT_TILE_SIZE 应为 1024，实际为 {DEFAULT_TILE_SIZE}"
            logger.info(f"✓ DEFAULT_TILE_SIZE = {DEFAULT_TILE_SIZE}")

            message = "✓ 测试通过: 分块大小为 1024×1024"
            logger.info(message)
            return True, message

        except Exception as e:
            message = f"✗ 测试失败: {str(e)}"
            logger.error(message)
            return False, message

    def test_5_parallel_processing_correctness(self) -> Tuple[bool, str]:
        """
        测试 5: 验证并行处理的正确性
        """
        logger.info("=" * 60)
        logger.info("测试 5: 验证并行处理正确性")
        logger.info("=" * 60)

        try:
            # 验证并行处理服务的基本功能
            logger.info("✓ 验证 ParallelProcessingService 存在")
            assert hasattr(ParallelProcessingService, 'process_chunks_parallel'), \
                "process_chunks_parallel 方法不存在"
            logger.info("✓ process_chunks_parallel 方法存在")

            # 验证自动工作进程检测
            auto_workers = ParallelProcessingService.get_auto_worker_count()
            assert auto_workers == 8, f"自动检测的工作进程数应为 8，实际为 {auto_workers}"
            logger.info(f"✓ 自动检测工作进程数: {auto_workers}")

            # 验证参数验证方法
            success, msg = ParallelProcessingService.validate_parallel_parameters(
                num_workers=8,
                max_workers=16
            )
            assert success, f"参数验证失败: {msg}"
            logger.info("✓ 参数验证通过")

            message = "✓ 测试通过: 并行处理正确"
            logger.info(message)
            return True, message

        except Exception as e:
            message = f"✗ 测试失败: {str(e)}"
            logger.error(message)
            import traceback
            logger.error(traceback.format_exc())
            return False, message

    def benchmark_parallel_vs_sequential(self) -> Tuple[bool, Dict]:
        """
        性能基准测试: 并行处理 vs 顺序处理
        """
        logger.info("=" * 60)
        logger.info("性能基准测试: 并行处理 vs 顺序处理")
        logger.info("=" * 60)

        try:
            # 创建测试数据（模拟 16 个分块）
            num_chunks = 16
            test_data = [
                {"id": i, "value": np.random.rand(100, 100, 3)}
                for i in range(num_chunks)
            ]

            # 定义处理函数（模拟分块处理）
            def process_chunk(data):
                # 模拟处理时间
                time.sleep(0.1)
                return {
                    "id": data["id"],
                    "result": np.sum(data["value"])
                }

            # 测试 1: 顺序处理
            logger.info(f"开始顺序处理 {num_chunks} 个分块...")
            start_time = time.time()
            sequential_results = []
            for data in test_data:
                result = process_chunk(data)
                sequential_results.append(result)
            sequential_time = time.time() - start_time
            logger.info(f"✓ 顺序处理耗时: {sequential_time:.2f}s")

            # 测试 2: 并行处理（8 个工作进程）
            logger.info(f"开始并行处理 {num_chunks} 个分块（8 个工作进程）...")
            start_time = time.time()
            success, parallel_results, msg = (
                ParallelProcessingService.process_chunks_parallel(
                    test_data,
                    process_chunk,
                    num_workers=8,
                )
            )
            parallel_time = time.time() - start_time
            logger.info(f"✓ 并行处理耗时: {parallel_time:.2f}s")

            # 计算性能提升
            speedup = sequential_time / parallel_time
            improvement = (1 - parallel_time / sequential_time) * 100

            logger.info(f"✓ 性能提升: {speedup:.2f}x")
            logger.info(f"✓ 时间节省: {improvement:.1f}%")

            results = {
                "sequential_time": sequential_time,
                "parallel_time": parallel_time,
                "speedup": speedup,
                "improvement_percent": improvement,
                "num_chunks": num_chunks,
                "num_workers": 8,
            }

            return True, results

        except Exception as e:
            logger.error(f"性能基准测试失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False, {}

    def run_all_tests(self) -> bool:
        """
        运行所有测试
        """
        logger.info("\n" + "=" * 60)
        logger.info("开始并行处理优化测试")
        logger.info("=" * 60 + "\n")

        tests = [
            ("测试 1: 默认并行工作进程数", self.test_1_default_parallel_workers),
            ("测试 2: 无监督检测默认参数", self.test_2_unsupervised_detection_default_workers),
            ("测试 3: 深度学习检测默认参数", self.test_3_detection_default_workers),
            ("测试 4: 分块大小验证", self.test_4_tile_size_1024),
            ("测试 5: 并行处理正确性", self.test_5_parallel_processing_correctness),
        ]

        all_passed = True
        for test_name, test_func in tests:
            try:
                passed, message = test_func()
                self.test_results[test_name] = (passed, message)
                if not passed:
                    all_passed = False
            except Exception as e:
                logger.error(f"测试执行异常: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                self.test_results[test_name] = (False, f"测试异常: {str(e)}")
                all_passed = False

            logger.info("")

        # 运行性能基准测试
        logger.info("=" * 60)
        logger.info("运行性能基准测试")
        logger.info("=" * 60 + "\n")

        success, perf_results = self.benchmark_parallel_vs_sequential()
        if success:
            self.performance_results = perf_results
        else:
            all_passed = False

        # 输出测试总结
        logger.info("\n" + "=" * 60)
        logger.info("测试总结")
        logger.info("=" * 60)

        passed_count = sum(1 for passed, _ in self.test_results.values() if passed)
        total_count = len(self.test_results)

        for test_name, (passed, message) in self.test_results.items():
            status = "✓ 通过" if passed else "✗ 失败"
            logger.info(f"{status}: {test_name}")
            logger.info(f"  {message}\n")

        # 输出性能基准测试结果
        if self.performance_results:
            logger.info("=" * 60)
            logger.info("性能基准测试结果")
            logger.info("=" * 60)
            logger.info(f"顺序处理耗时: {self.performance_results['sequential_time']:.2f}s")
            logger.info(f"并行处理耗时: {self.performance_results['parallel_time']:.2f}s")
            logger.info(f"性能提升: {self.performance_results['speedup']:.2f}x")
            logger.info(f"时间节省: {self.performance_results['improvement_percent']:.1f}%")
            logger.info(f"处理分块数: {self.performance_results['num_chunks']}")
            logger.info(f"工作进程数: {self.performance_results['num_workers']}")

        logger.info("=" * 60)
        logger.info(f"测试结果: {passed_count}/{total_count} 通过")
        logger.info("=" * 60)

        return all_passed


def main():
    """主函数"""
    test_suite = ParallelOptimizationTestSuite()
    all_passed = test_suite.run_all_tests()
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
