"""
影像处理服务模块
用于处理多时相遥感影像的归一化、波段选择和尺寸统一
"""

import numpy as np
from pathlib import Path
from typing import Tuple, List, Optional, Dict
import logging

from backend.utils.image_reader import ImageReader

logger = logging.getLogger(__name__)


class ImageProcessingService:
    """影像处理服务类"""

    @staticmethod
    def normalize_image(
        image_data: np.ndarray, method: str = "minmax"
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        对影像进行归一化处理

        Args:
            image_data: 影像数据数组 (H, W, C)
            method: 归一化方法，支持 'minmax' 和 'zscore'

        Returns:
            (处理是否成功, 归一化后的影像数据, 错误信息或成功消息)
        """
        try:
            if image_data is None or image_data.size == 0:
                return False, None, "影像数据为空"

            normalized_data = image_data.copy()

            if method == "minmax":
                # Min-Max 归一化：(x - min) / (max - min)
                for band_idx in range(image_data.shape[2]):
                    band_data = image_data[:, :, band_idx]
                    band_min = np.min(band_data)
                    band_max = np.max(band_data)

                    if band_max - band_min == 0:
                        # 如果最大值等于最小值，设置为 0
                        normalized_data[:, :, band_idx] = 0
                    else:
                        normalized_data[:, :, band_idx] = (
                            band_data - band_min
                        ) / (band_max - band_min)

            elif method == "zscore":
                # Z-Score 归一化：(x - mean) / std
                for band_idx in range(image_data.shape[2]):
                    band_data = image_data[:, :, band_idx]
                    band_mean = np.mean(band_data)
                    band_std = np.std(band_data)

                    if band_std == 0:
                        # 如果标准差为 0，设置为 0
                        normalized_data[:, :, band_idx] = 0
                    else:
                        normalized_data[:, :, band_idx] = (
                            band_data - band_mean
                        ) / band_std

            else:
                return False, None, f"不支持的归一化方法: {method}"

            return True, normalized_data, "影像归一化成功"

        except Exception as e:
            logger.error(f"影像归一化失败: {str(e)}")
            return False, None, f"影像归一化失败: {str(e)}"

    @staticmethod
    def select_bands(
        image_data: np.ndarray, band_indices: Optional[List[int]] = None
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        选择指定的波段

        Args:
            image_data: 影像数据数组 (H, W, C)
            band_indices: 要选择的波段索引列表（从 0 开始）
                         如果为 None，则返回所有波段

        Returns:
            (处理是否成功, 选择后的影像数据, 错误信息或成功消息)
        """
        try:
            if image_data is None or image_data.size == 0:
                return False, None, "影像数据为空"

            # 如果未指定波段，返回所有波段
            if band_indices is None:
                return True, image_data, "未指定波段，返回所有波段"

            # 检查波段索引是否有效
            max_band_idx = image_data.shape[2] - 1
            for band_idx in band_indices:
                if band_idx < 0 or band_idx > max_band_idx:
                    return (
                        False,
                        None,
                        f"波段索引超出范围: {band_idx}（有效范围: 0-{max_band_idx}）",
                    )

            # 选择指定波段
            selected_data = image_data[:, :, band_indices]

            return True, selected_data, "波段选择成功"

        except Exception as e:
            logger.error(f"波段选择失败: {str(e)}")
            return False, None, f"波段选择失败: {str(e)}"

    @staticmethod
    def resize_image(
        image_data: np.ndarray, target_height: int, target_width: int
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        调整影像尺寸

        Args:
            image_data: 影像数据数组 (H, W, C)
            target_height: 目标高度
            target_width: 目标宽度

        Returns:
            (处理是否成功, 调整后的影像数据, 错误信息或成功消息)
        """
        try:
            if image_data is None or image_data.size == 0:
                return False, None, "影像数据为空"

            from cv2 import resize, INTER_LINEAR

            # 获取原始尺寸
            original_height, original_width = image_data.shape[:2]

            # 如果尺寸相同，直接返回
            if original_height == target_height and original_width == target_width:
                return True, image_data, "影像尺寸已相同，无需调整"

            # 调整每个波段的尺寸
            resized_data = np.zeros(
                (target_height, target_width, image_data.shape[2]),
                dtype=image_data.dtype,
            )

            for band_idx in range(image_data.shape[2]):
                band_data = image_data[:, :, band_idx]
                resized_band = resize(
                    band_data, (target_width, target_height), interpolation=INTER_LINEAR
                )
                resized_data[:, :, band_idx] = resized_band

            logger.info(
                f"影像尺寸调整: {original_height}x{original_width} -> {target_height}x{target_width}"
            )

            return True, resized_data, "影像尺寸调整成功"

        except Exception as e:
            logger.error(f"影像尺寸调整失败: {str(e)}")
            return False, None, f"影像尺寸调整失败: {str(e)}"

    @staticmethod
    def unify_image_sizes(
        images: List[np.ndarray],
    ) -> Tuple[bool, Optional[List[np.ndarray]], str]:
        """
        统一多个影像的尺寸

        Args:
            images: 影像数据数组列表

        Returns:
            (处理是否成功, 统一尺寸后的影像列表, 错误信息或成功消息)
        """
        try:
            if not images or len(images) == 0:
                return False, None, "影像列表为空"

            # 获取最小的尺寸作为目标尺寸
            min_height = min(img.shape[0] for img in images)
            min_width = min(img.shape[1] for img in images)

            logger.info(f"统一影像尺寸为: {min_height}x{min_width}")

            # 调整所有影像到最小尺寸
            unified_images = []
            for image_data in images:
                success, resized_data, message = ImageProcessingService.resize_image(
                    image_data, min_height, min_width
                )

                if not success:
                    return False, None, f"尺寸统一失败: {message}"

                unified_images.append(resized_data)

            return True, unified_images, "影像尺寸统一成功"

        except Exception as e:
            logger.error(f"影像尺寸统一失败: {str(e)}")
            return False, None, f"影像尺寸统一失败: {str(e)}"

    @staticmethod
    def process_multitemporal_images(
        image_paths: List[str],
        normalize: bool = True,
        band_indices: Optional[List[int]] = None,
        unify_size: bool = True,
    ) -> Tuple[bool, Optional[List[np.ndarray]], str]:
        """
        处理多时相影像序列

        按文件名顺序组织多时相影像为时间序列，完成归一化、波段选择与尺寸统一

        Args:
            image_paths: 影像文件路径列表（应按时间顺序排列）
            normalize: 是否进行归一化
            band_indices: 要选择的波段索引列表
            unify_size: 是否统一影像尺寸

        Returns:
            (处理是否成功, 处理后的影像列表, 错误信息或成功消息)
        """
        try:
            # 读取所有影像
            success, images, message = ImageReader.read_multiple_images(image_paths)
            if not success:
                return False, None, message

            logger.info(f"已读取 {len(images)} 个时相影像")

            # 波段选择
            if band_indices is not None:
                selected_images = []
                for image_data in images:
                    success, selected_data, message = (
                        ImageProcessingService.select_bands(image_data, band_indices)
                    )
                    if not success:
                        return False, None, message
                    selected_images.append(selected_data)
                images = selected_images
                logger.info(f"已选择波段: {band_indices}")

            # 尺寸统一
            if unify_size:
                success, images, message = ImageProcessingService.unify_image_sizes(
                    images
                )
                if not success:
                    return False, None, message

            # 归一化
            if normalize:
                normalized_images = []
                for image_data in images:
                    success, normalized_data, message = (
                        ImageProcessingService.normalize_image(image_data)
                    )
                    if not success:
                        return False, None, message
                    normalized_images.append(normalized_data)
                images = normalized_images
                logger.info("已完成影像归一化")

            return True, images, "多时相影像处理成功"

        except Exception as e:
            logger.error(f"多时相影像处理失败: {str(e)}")
            return False, None, f"多时相影像处理失败: {str(e)}"
