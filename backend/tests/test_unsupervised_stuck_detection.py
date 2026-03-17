"""
测试非监督分类任务"提取目标中心点"时卡住的问题

测试目标：
1. 验证并行处理超时break问题
2. 验证进度更新间隔过大导致"卡住"误判
3. 验证中心点提取阶段缺少停止标志检查

测试文件：/Users/wuchenkai/解译程序/20201023.tif
"""

import sys
import os
import time
import numpy as np
import logging

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.services.unsupervised_detection import UnsupervisedDiseaseDetectionService
from backend.services.parallel_processing import ParallelProcessingService
from backend.services.background_task_manager import BackgroundTaskManager
from backend.utils.image_reader import ImageReader
from backend.utils.tile_utils import TilingService, Tile

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestUnsupervisedStuckDetection:
    """测试非监督分类任务卡住问题"""

    def __init__(self):
        self.test_image_path = "/Users/wuchenkai/解译程序/20201023.tif"
        self.detection_service = UnsupervisedDiseaseDetectionService()
        self.parallel_service = ParallelProcessingService()
        self.task_manager = BackgroundTaskManager()

    def test_image_reading(self):
        """测试图像读取"""
        logger.info("=" * 60)
        logger.info("测试1：图像读取")
        logger.info("=" * 60)

        try:
            start_time = time.time()
            success, image_data, message = ImageReader.read_image(self.test_image_path)
            end_time = time.time()

            if not success:
                logger.error(f"✗ 图像读取失败: {message}")
                return None, None

            H, W, C = image_data.shape
            logger.info(f"✓ 图像读取成功")
            logger.info(f"  - 尺寸: {W} x {H} x {C}")
            logger.info(f"  - 数据类型: {image_data.dtype}")
            logger.info(f"  - 读取时间: {end_time - start_time:.2f}秒")

            # 判断是否需要分块
            needs_tiling = H > 5000 or W > 5000
            logger.info(f"  - 是否需要分块: {needs_tiling}")

            return image_data, None

        except Exception as e:
            logger.error(f"✗ 图像读取失败: {e}")
            return None, None

    def test_tile_generation(self, image_data):
        """测试分块生成"""
        logger.info("=" * 60)
        logger.info("测试2：分块生成")
        logger.info("=" * 60)

        try:
            H, W, C = image_data.shape
            logger.info(f"原始图像尺寸: {W} x {H} x {C}")

            start_time = time.time()
            success, tiles, msg = TilingService.generate_tiles(
                image_data,
                tile_size=5000,
                padding_mode="pad"
            )
            end_time = time.time()

            if not success:
                logger.error(f"✗ 分块生成失败: {msg}")
                return None

            logger.info(f"✓ 分块生成成功")
            logger.info(f"  - 分块数量: {len(tiles)}")
            logger.info(f"  - 生成时间: {end_time - start_time:.2f}秒")

            # 显示前几个分块的信息
            for i, tile in enumerate(tiles[:3]):
                logger.info(f"  - 分块{i}: {tile.data.shape}, 起始位置({tile.offset_x}, {tile.offset_y})")

            return tiles

        except Exception as e:
            logger.error(f"✗ 分块生成失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def test_parallel_processing_timeout(self, tiles):
        """测试并行处理超时问题"""
        logger.info("=" * 60)
        logger.info("测试3：并行处理超时问题")
        logger.info("=" * 60)

        try:
            # 创建测试任务
            task_id = f"test_timeout_{int(time.time())}"
            self.task_manager.create_task(
                task_id=task_id,
                task_type="unsupervised_detection",
                params={
                    "tile_count": len(tiles),
                    "test_mode": True
                }
            )
            self.task_manager.start_task(task_id)

            # 只处理前10个分块，以快速测试超时逻辑
            test_tiles = tiles[:10]
            logger.info(f"测试分块数量: {len(test_tiles)}")

            start_time = time.time()

            # 模拟处理每个分块的函数
            def process_tile_wrapper(tile):
                """包装处理函数，模拟长时间运行"""
                import random
                time.sleep(random.uniform(1, 3))  # 随机延迟1-3秒

                # 简单的特征构建和聚类
                from sklearn.cluster import KMeans
                tile_data = tile.data.reshape(-1, tile.data.shape[2])

                # 使用更少的样本点，加快处理速度
                sample_indices = np.random.choice(
                    len(tile_data),
                    size=min(1000, len(tile_data)),
                    replace=False
                )
                sampled_data = tile_data[sample_indices]

                # 简单聚类
                kmeans = KMeans(n_clusters=2, random_state=42)
                labels = kmeans.fit_predict(sampled_data)

                # 创建mask
                mask = np.zeros((tile.height, tile.width), dtype=np.uint8)
                mask[sample_indices[labels == 1]] = 1

                return {
                    "tile_index": tile.index,
                    "mask": mask,
                    "success": True
                }

            # 并行处理
            success, results, errors, message = self.parallel_service.process_tiles_parallel(
                test_tiles,
                process_tile_wrapper,
                task_manager=self.task_manager,
                task_id=task_id,
                error_handling="log"
            )

            end_time = time.time()

            logger.info(f"✓ 并行处理完成")
            logger.info(f"  - 处理时间: {end_time - start_time:.2f}秒")
            logger.info(f"  - 成功: {success}")
            logger.info(f"  - 结果数量: {len(results) if results else 0}")
            logger.info(f"  - 错误数量: {len(errors) if errors else 0}")
            logger.info(f"  - 消息: {message}")

            # 检查是否有超时错误
            timeout_errors = [e for e in errors if e.get('stage') == 'result_collection']
            if timeout_errors:
                logger.warning(f"⚠ 检测到超时错误: {len(timeout_errors)}个")
                for error in timeout_errors:
                    logger.warning(f"  - {error}")

            return success, results, errors

        except Exception as e:
            logger.error(f"✗ 并行处理测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False, None, []

    def test_progress_update_interval(self):
        """测试进度更新间隔"""
        logger.info("=" * 60)
        logger.info("测试4：进度更新间隔")
        logger.info("=" * 60)

        # 测试不同的特征数量
        test_cases = [
            (5, "少量特征"),
            (50, "中等特征"),
            (500, "大量特征"),
            (5000, "超多特征"),
        ]

        for num_features, desc in test_cases:
            log_interval = max(1, num_features // 10)
            logger.info(f"{desc} ({num_features}个特征):")
            logger.info(f"  - 进度更新间隔: 每{log_interval}个区域")
            logger.info(f"  - 进度更新次数: {num_features // log_interval}")

            # 假设每个区域需要处理时间
            avg_process_time = 0.1  # 100ms
            total_update_time = log_interval * avg_process_time

            # 卡死阈值
            stuck_threshold = 30  # 30秒

            if total_update_time > stuck_threshold:
                logger.warning(f"  ⚠ 警告: 进度更新间隔({total_update_time:.2f}秒) > 卡死阈值({stuck_threshold}秒)")
                logger.warning(f"     可能被误判为'卡住'")
            else:
                logger.info(f"  ✓ 进度更新间隔({total_update_time:.2f}秒) < 卡死阈值({stuck_threshold}秒)")

    def test_center_point_extraction_progress(self):
        """测试中心点提取阶段的进度更新"""
        logger.info("=" * 60)
        logger.info("测试5：中心点提取阶段进度更新")
        logger.info("=" * 60)

        # 模拟不同数量的连通域
        test_cases = [
            (10, "少量连通域"),
            (100, "中等连通域"),
            (1000, "大量连通域"),
            (10000, "超多连通域"),
        ]

        for num_features, desc in test_cases:
            log_interval = max(1, num_features // 10)
            progress_range = 5  # 90% -> 95%

            logger.info(f"{desc} ({num_features}个连通域):")
            logger.info(f"  - 进度更新间隔: 每{log_interval}个区域")
            logger.info(f"  - 进度更新次数: {num_features // log_interval}")
            logger.info(f"  - 每次进度增量: {progress_range / (num_features // log_interval):.2f}%")

            # 假设每个区域需要处理时间
            avg_process_time = 0.01  # 10ms
            total_time = num_features * avg_process_time

            logger.info(f"  - 预计总处理时间: {total_time:.2f}秒")

            # 卡死阈值
            stuck_threshold = 30  # 30秒

            if total_time > stuck_threshold:
                logger.warning(f"  ⚠ 警告: 预计处理时间({total_time:.2f}秒) > 卡死阈值({stuck_threshold}秒)")
                logger.warning(f"     可能被误判为'卡住'")
            else:
                logger.info(f"  ✓ 预计处理时间({total_time:.2f}秒) < 卡死阈值({stuck_threshold}秒)")

    def test_stop_flag_checking(self):
        """测试停止标志检查"""
        logger.info("=" * 60)
        logger.info("测试6：停止标志检查")
        logger.info("=" * 60)

        # 创建测试任务
        task_id = f"test_stop_{int(time.time())}"
        self.task_manager.create_task(
            task_id=task_id,
            task_type="unsupervised_detection",
            params={}
        )
        self.task_manager.start_task(task_id)

        logger.info(f"测试任务ID: {task_id}")

        # 模拟中心点提取循环（大影像路径）
        logger.info("模拟大影像路径的中心点提取循环...")

        num_features = 1000
        log_interval = max(1, num_features // 10)

        # 模拟停止标志检查
        stop_requested = False
        processed_regions = 0

        for region_id in range(1, num_features + 1):
            # 模拟处理
            processed_regions += 1

            # 当前代码：没有检查停止标志
            # if self.task_manager.is_stop_requested(task_id):
            #     logger.info(f"任务被停止（区域{region_id}/{num_features}）")
            #     break

            # 进度更新
            if region_id % log_interval == 0:
                progress = 90 + int((region_id / num_features) * 5)
                logger.info(f"进度: {progress}%, 区域: {region_id}/{num_features}")

            # 模拟用户在50%时请求停止
            if region_id == num_features // 2:
                logger.info(f"模拟用户请求停止任务（区域{region_id}/{num_features}）")
                stop_requested = True

            # 当前代码不会响应停止请求
            if stop_requested and processed_regions == num_features:
                logger.warning("⚠ 警告: 当前代码在中心点提取阶段无法响应停止请求")
                logger.warning("  - 用户请求停止，但任务继续执行")
                logger.warning("  - 建议: 在循环中增加停止标志检查")

        logger.info(f"✓ 测试完成，处理了{processed_regions}个区域")

    def run_all_tests(self):
        """运行所有测试"""
        logger.info("=" * 60)
        logger.info("开始测试非监督分类任务卡住问题")
        logger.info("=" * 60)

        # 测试1：图像读取
        image_data, nodata_value = self.test_image_reading()
        if image_data is None:
            logger.error("图像读取失败，跳过后续测试")
            return

        # 测试2：分块生成
        tiles = self.test_tile_generation(image_data)
        if tiles is None:
            logger.error("分块生成失败，跳过后续测试")
            return

        # 测试3：并行处理超时
        self.test_parallel_processing_timeout(tiles)

        # 测试4：进度更新间隔
        self.test_progress_update_interval()

        # 测试5：中心点提取进度
        self.test_center_point_extraction_progress()

        # 测试6：停止标志检查
        self.test_stop_flag_checking()

        logger.info("=" * 60)
        logger.info("所有测试完成")
        logger.info("=" * 60)


if __name__ == "__main__":
    tester = TestUnsupervisedStuckDetection()
    tester.run_all_tests()