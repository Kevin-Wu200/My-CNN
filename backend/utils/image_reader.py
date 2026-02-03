"""
影像读取工具模块
用于读取 IMG 遥感影像文件并提取影像数据
"""

import numpy as np
from pathlib import Path
from typing import Tuple, Optional, List
import logging
from osgeo import gdal

logger = logging.getLogger(__name__)

# 启用 GDAL 异常
gdal.UseExceptions()


class ImageReader:
    """影像读取工具类"""

    @staticmethod
    def read_image(image_path: str) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        读取单个 IMG 影像文件

        Args:
            image_path: 影像文件路径

        Returns:
            (读取是否成功, 影像数据数组, 错误信息或成功消息)
        """
        try:
            image_path = Path(image_path)

            # 检查文件是否存在
            if not image_path.exists():
                return False, None, f"影像文件不存在: {image_path}"

            # 使用 GDAL 打开影像
            dataset = gdal.Open(str(image_path))
            if dataset is None:
                return False, None, f"无法打开影像文件: {image_path}"

            # 获取影像基本信息
            width = dataset.RasterXSize
            height = dataset.RasterYSize
            band_count = dataset.RasterCount

            logger.info(
                f"影像信息 - 宽: {width}, 高: {height}, 波段数: {band_count}"
            )

            # 读取所有波段数据
            image_data = np.zeros((height, width, band_count), dtype=np.float32)

            for band_idx in range(band_count):
                band = dataset.GetRasterBand(band_idx + 1)
                if band is None:
                    return False, None, f"无法读取第 {band_idx + 1} 波段"

                band_data = band.ReadAsArray()
                if band_data is None:
                    return False, None, f"波段 {band_idx + 1} 数据为空"

                image_data[:, :, band_idx] = band_data.astype(np.float32)

            # 关闭数据集
            dataset = None

            return True, image_data, "影像读取成功"

        except Exception as e:
            logger.error(f"读取影像时出错: {str(e)}")
            return False, None, f"读取影像失败: {str(e)}"

    @staticmethod
    def read_image_chunk(
        image_path: str, chunk_x: int, chunk_y: int, chunk_width: int, chunk_height: int
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        按指定块大小读取影像的一部分

        Args:
            image_path: 影像文件路径
            chunk_x: 块的起始 X 坐标（像素）
            chunk_y: 块的起始 Y 坐标（像素）
            chunk_width: 块的宽度（像素）
            chunk_height: 块的高度（像素）

        Returns:
            (读取是否成功, 影像块数据数组, 错误信息或成功消息)
        """
        try:
            image_path = Path(image_path)

            # 检查文件是否存在
            if not image_path.exists():
                return False, None, f"影像文件不存在: {image_path}"

            # 使用 GDAL 打开影像
            dataset = gdal.Open(str(image_path))
            if dataset is None:
                return False, None, f"无法打开影像文件: {image_path}"

            # 获取影像基本信息
            width = dataset.RasterXSize
            height = dataset.RasterYSize
            band_count = dataset.RasterCount

            # 检查块坐标是否有效
            if chunk_x < 0 or chunk_y < 0:
                return False, None, "块坐标不能为负数"

            if chunk_x + chunk_width > width or chunk_y + chunk_height > height:
                return False, None, "块超出影像范围"

            # 读取指定块的数据
            chunk_data = np.zeros(
                (chunk_height, chunk_width, band_count), dtype=np.float32
            )

            for band_idx in range(band_count):
                band = dataset.GetRasterBand(band_idx + 1)
                if band is None:
                    return False, None, f"无法读取第 {band_idx + 1} 波段"

                band_data = band.ReadArray(chunk_x, chunk_y, chunk_width, chunk_height)
                if band_data is None:
                    return False, None, f"波段 {band_idx + 1} 块数据为空"

                chunk_data[:, :, band_idx] = band_data.astype(np.float32)

            # 关闭数据集
            dataset = None

            return True, chunk_data, "影像块读取成功"

        except Exception as e:
            logger.error(f"读取影像块时出错: {str(e)}")
            return False, None, f"读取影像块失败: {str(e)}"

    @staticmethod
    def get_image_info(image_path: str) -> Tuple[bool, Optional[dict], str]:
        """
        获取影像的基本信息

        Args:
            image_path: 影像文件路径

        Returns:
            (获取是否成功, 影像信息字典, 错误信息或成功消息)
        """
        try:
            image_path = Path(image_path)

            # 检查文件是否存在
            if not image_path.exists():
                return False, None, f"影像文件不存在: {image_path}"

            # 使用 GDAL 打开影像
            dataset = gdal.Open(str(image_path))
            if dataset is None:
                return False, None, f"无法打开影像文件: {image_path}"

            # 获取影像信息
            info = {
                "width": dataset.RasterXSize,
                "height": dataset.RasterYSize,
                "band_count": dataset.RasterCount,
                "data_type": dataset.GetRasterBand(1).DataType,
                "projection": dataset.GetProjection(),
                "geotransform": dataset.GetGeoTransform(),
            }

            # 关闭数据集
            dataset = None

            return True, info, "影像信息获取成功"

        except Exception as e:
            logger.error(f"获取影像信息时出错: {str(e)}")
            return False, None, f"获取影像信息失败: {str(e)}"

    @staticmethod
    def read_multiple_images(image_paths: List[str]) -> Tuple[bool, Optional[List[np.ndarray]], str]:
        """
        读取多个影像文件

        Args:
            image_paths: 影像文件路径列表

        Returns:
            (读取是否成功, 影像数据数组列表, 错误信息或成功消息)
        """
        images = []

        for image_path in image_paths:
            success, image_data, message = ImageReader.read_image(image_path)
            if not success:
                return False, None, f"读取影像失败: {message}"

            images.append(image_data)

        return True, images, "所有影像读取成功"
