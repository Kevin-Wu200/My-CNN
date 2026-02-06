"""
影像读取工具模块
用于读取 IMG 遥感影像文件并提取影像数据
"""

import numpy as np
from pathlib import Path
from typing import Tuple, Optional, List
import logging
import os
from osgeo import gdal

logger = logging.getLogger(__name__)

# 启用 GDAL 异常
gdal.UseExceptions()

# 文件大小限制（20GB）
# 注意：真实的遥感影像可能达到4GB或更大
# 原始限制500MB过小，已调整为20GB以支持大型遥感影像
MAX_FILE_SIZE = 20 * 1024 * 1024 * 1024


class ImageReader:
    """影像读取工具类"""

    @staticmethod
    def _validate_file(image_path: str) -> Tuple[bool, str]:
        """
        验证文件是否可以读取

        Args:
            image_path: 影像文件路径

        Returns:
            (验证是否通过, 错误信息)
        """
        try:
            file_path = Path(image_path)

            # 检查文件是否存在
            if not file_path.exists():
                return False, f"文件不存在: {image_path}"

            # 检查文件是否可读
            if not os.access(str(file_path), os.R_OK):
                return False, f"文件不可读（权限问题）: {image_path}"

            # 检查文件大小
            file_size = file_path.stat().st_size
            if file_size <= 0:
                return False, f"文件大小无效: {file_size} bytes"

            if file_size > MAX_FILE_SIZE:
                return False, f"文件过大: {file_size} bytes (限制: {MAX_FILE_SIZE} bytes)"

            logger.info(f"[FILE_VALIDATION_PASS] filePath={image_path}, fileSize={file_size}")
            return True, ""

        except Exception as e:
            return False, f"文件验证失败: {str(e)}"

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

            # 第一步：验证文件
            valid, error_msg = ImageReader._validate_file(str(image_path))
            if not valid:
                logger.error(f"[FILE_VALIDATION_FAILED] filePath={image_path}, error={error_msg}")
                return False, None, error_msg

            logger.info(f"[FILE_VALIDATION_PASS] filePath={image_path}")

            # 使用 GDAL 打开影像
            dataset = gdal.Open(str(image_path))
            if dataset is None:
                error_msg = f"无法打开影像文件: {image_path}"
                logger.error(f"[GDAL_OPEN_FAILED] filePath={image_path}, error={error_msg}")
                return False, None, error_msg

            # 获取影像基本信息
            width = dataset.RasterXSize
            height = dataset.RasterYSize
            band_count = dataset.RasterCount

            logger.info(
                f"[IMAGE_INFO] filePath={image_path}, width={width}, height={height}, bands={band_count}"
            )

            # 读取所有波段数据
            image_data = np.zeros((height, width, band_count), dtype=np.float32)

            for band_idx in range(band_count):
                band = dataset.GetRasterBand(band_idx + 1)
                if band is None:
                    error_msg = f"无法读取第 {band_idx + 1} 波段"
                    logger.error(f"[BAND_READ_FAILED] filePath={image_path}, band={band_idx + 1}")
                    return False, None, error_msg

                band_data = band.ReadAsArray()
                if band_data is None:
                    error_msg = f"波段 {band_idx + 1} 数据为空"
                    logger.error(f"[BAND_DATA_EMPTY] filePath={image_path}, band={band_idx + 1}")
                    return False, None, error_msg

                image_data[:, :, band_idx] = band_data.astype(np.float32)

            # 关闭数据集
            dataset = None

            logger.info(f"[IMAGE_READ_SUCCESS] filePath={image_path}, shape={image_data.shape}")
            return True, image_data, "影像读取成功"

        except Exception as e:
            logger.error(f"[IMAGE_READ_ERROR] filePath={image_path}, error={str(e)}")
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

            # 第一步：验证文件
            valid, error_msg = ImageReader._validate_file(str(image_path))
            if not valid:
                logger.error(f"[FILE_VALIDATION_FAILED] filePath={image_path}, error={error_msg}")
                return False, None, error_msg

            logger.info(f"[FILE_VALIDATION_PASS] filePath={image_path}")

            # 使用 GDAL 打开影像
            dataset = gdal.Open(str(image_path))
            if dataset is None:
                error_msg = f"无法打开影像文件: {image_path}"
                logger.error(f"[GDAL_OPEN_FAILED] filePath={image_path}")
                return False, None, error_msg

            # 获取影像基本信息
            width = dataset.RasterXSize
            height = dataset.RasterYSize
            band_count = dataset.RasterCount

            # 检查块坐标是否有效
            if chunk_x < 0 or chunk_y < 0:
                error_msg = "块坐标不能为负数"
                logger.error(f"[CHUNK_COORD_INVALID] filePath={image_path}, x={chunk_x}, y={chunk_y}")
                return False, None, error_msg

            if chunk_x + chunk_width > width or chunk_y + chunk_height > height:
                error_msg = "块超出影像范围"
                logger.error(f"[CHUNK_OUT_OF_BOUNDS] filePath={image_path}, bounds=({chunk_x},{chunk_y},{chunk_width},{chunk_height}), imageSize=({width},{height})")
                return False, None, error_msg

            # 读取指定块的数据
            chunk_data = np.zeros(
                (chunk_height, chunk_width, band_count), dtype=np.float32
            )

            for band_idx in range(band_count):
                band = dataset.GetRasterBand(band_idx + 1)
                if band is None:
                    error_msg = f"无法读取第 {band_idx + 1} 波段"
                    logger.error(f"[BAND_READ_FAILED] filePath={image_path}, band={band_idx + 1}")
                    return False, None, error_msg

                band_data = band.ReadArray(chunk_x, chunk_y, chunk_width, chunk_height)
                if band_data is None:
                    error_msg = f"波段 {band_idx + 1} 块数据为空"
                    logger.error(f"[BAND_DATA_EMPTY] filePath={image_path}, band={band_idx + 1}")
                    return False, None, error_msg

                chunk_data[:, :, band_idx] = band_data.astype(np.float32)

            # 关闭数据集
            dataset = None

            logger.info(f"[CHUNK_READ_SUCCESS] filePath={image_path}, chunk=({chunk_x},{chunk_y},{chunk_width},{chunk_height})")
            return True, chunk_data, "影像块读取成功"

        except Exception as e:
            logger.error(f"[CHUNK_READ_ERROR] filePath={image_path}, error={str(e)}")
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

            # 第一步：验证文件
            valid, error_msg = ImageReader._validate_file(str(image_path))
            if not valid:
                logger.error(f"[FILE_VALIDATION_FAILED] filePath={image_path}, error={error_msg}")
                return False, None, error_msg

            logger.info(f"[FILE_VALIDATION_PASS] filePath={image_path}")

            # 使用 GDAL 打开影像
            dataset = gdal.Open(str(image_path))
            if dataset is None:
                error_msg = f"无法打开影像文件: {image_path}"
                logger.error(f"[GDAL_OPEN_FAILED] filePath={image_path}")
                return False, None, error_msg

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

            logger.info(f"[IMAGE_INFO_SUCCESS] filePath={image_path}, info={info}")
            return True, info, "影像信息获取成功"

        except Exception as e:
            logger.error(f"[IMAGE_INFO_ERROR] filePath={image_path}, error={str(e)}")
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
        if not image_paths:
            error_msg = "影像路径列表为空"
            logger.error(f"[MULTIPLE_IMAGES_EMPTY] error={error_msg}")
            return False, None, error_msg

        images = []
        failed_images = []

        for idx, image_path in enumerate(image_paths):
            logger.info(f"[READING_IMAGE] index={idx}, path={image_path}")
            success, image_data, message = ImageReader.read_image(image_path)
            if not success:
                logger.error(f"[IMAGE_READ_FAILED] index={idx}, path={image_path}, error={message}")
                failed_images.append((idx, image_path, message))
                # 继续读取其他影像，而不是立即返回失败
                continue

            images.append(image_data)

        # 如果有失败的影像，返回错误
        if failed_images:
            error_details = "; ".join([f"[{idx}] {path}: {msg}" for idx, path, msg in failed_images])
            error_msg = f"部分影像读取失败: {error_details}"
            logger.error(f"[MULTIPLE_IMAGES_PARTIAL_FAILURE] failed={len(failed_images)}, total={len(image_paths)}")
            return False, None, error_msg

        if not images:
            error_msg = "没有成功读取任何影像"
            logger.error(f"[MULTIPLE_IMAGES_ALL_FAILED] error={error_msg}")
            return False, None, error_msg

        logger.info(f"[MULTIPLE_IMAGES_SUCCESS] count={len(images)}, total={len(image_paths)}")
        return True, images, f"成功读取 {len(images)} 个影像"
