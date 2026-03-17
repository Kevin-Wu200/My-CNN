#!/usr/bin/env python3
"""
测试无监督分类功能
使用真实数据进行测试
"""

import sys
import os
import numpy as np
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.services.unsupervised_detection import UnsupervisedDiseaseDetectionService
from backend.utils.image_reader import ImageReader

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_unsupervised_detection(image_path: str):
    """
    测试无监督分类功能

    Args:
        image_path: 影像文件路径
    """
    logger.info("=" * 80)
    logger.info("开始测试无监督分类功能")
    logger.info("=" * 80)

    try:
        # 第一步：读取影像
        logger.info(f"正在读取影像: {image_path}")
        success, image_data, message = ImageReader.read_image(image_path)

        if not success:
            logger.error(f"读取影像失败: {message}")
            return False

        logger.info(f"影像读取成功，尺寸: {image_data.shape}")

        # 如果影像太大，裁剪一部分进行测试
        if image_data.shape[0] > 5000 or image_data.shape[1] > 5000:
            logger.warning("影像过大，裁剪中心区域进行测试")
            h, w = image_data.shape[:2]
            crop_h = min(3000, h)
            crop_w = min(3000, w)
            y_start = (h - crop_h) // 2
            x_start = (w - crop_w) // 2
            image_data = image_data[y_start:y_start+crop_h, x_start:x_start+crop_w]
            logger.info(f"裁剪后尺寸: {image_data.shape}")

        # 第二步：创建检测服务
        logger.info("创建无监督检测服务")
        service = UnsupervisedDiseaseDetectionService()

        # 第三步：执行检测
        logger.info("开始执行无监督检测")
        logger.info("-" * 80)

        # 检测参数
        n_clusters = 4
        min_area = 50
        tile_size = 1024
        padding_mode = "pad"
        use_parallel = True
        num_workers = 4

        logger.info(f"检测参数:")
        logger.info(f"  - n_clusters: {n_clusters}")
        logger.info(f"  - min_area: {min_area}")
        logger.info(f"  - tile_size: {tile_size}")
        logger.info(f"  - padding_mode: {padding_mode}")
        logger.info(f"  - use_parallel: {use_parallel}")
        logger.info(f"  - num_workers: {num_workers}")

        success, result, message = service.detect_on_tiled_image(
            image_data=image_data,
            n_clusters=n_clusters,
            min_area=min_area,
            nodata_value=None,
            tile_size=tile_size,
            padding_mode=padding_mode,
            use_parallel=use_parallel,
            num_workers=num_workers,
            task_manager=None,
            task_id=None,
        )

        logger.info("-" * 80)

        if not success:
            logger.error(f"检测失败: {message}")
            return False

        logger.info("检测成功！")
        logger.info(f"检测结果:")
        logger.info(f"  - 总点位数: {len(result.get('points', []))}")
        logger.info(f"  - 分块数: {result.get('n_tiles', 0)}")
        logger.info(f"  - 成功分块数: {result.get('n_successful_tiles', 0)}")
        logger.info(f"  - 总超像素数: {result.get('total_superpixels', 0)}")
        logger.info(f"  - 病害木超像素数: {result.get('total_positive', 0)}")
        logger.info(f"  - 分块尺寸: {result.get('tile_size', 0)}")
        logger.info(f"  - 影像尺寸: {result.get('image_size', (0, 0))}")

        # 显示前10个点位
        points = result.get('points', [])
        if points:
            logger.info(f"\n前10个检测点位:")
            for i, point in enumerate(points[:10]):
                logger.info(f"  {i+1}. ({point['x']:.1f}, {point['y']:.1f}) 面积={point.get('area', 'N/A')}")

        logger.info("=" * 80)
        logger.info("测试完成！")
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error(f"测试过程中发生异常: {str(e)}", exc_info=True)
        return False


if __name__ == "__main__":
    # 测试文件路径
    image_path = "/Users/wuchenkai/解译程序/20201023.tif"

    # 检查文件是否存在
    if not os.path.exists(image_path):
        logger.error(f"测试文件不存在: {image_path}")
        sys.exit(1)

    # 执行测试
    success = test_unsupervised_detection(image_path)

    # 退出
    sys.exit(0 if success else 1)
