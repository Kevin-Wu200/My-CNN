"""
SLIC 超像素处理工具模块
用于执行 SLIC 超像素分割和相关处理
"""

import numpy as np
from pathlib import Path
from typing import Tuple, Optional, Dict, List
import logging
from skimage.segmentation import slic
from skimage.color import rgb2gray

logger = logging.getLogger(__name__)


class SLICProcessor:
    """SLIC 超像素处理工具类"""

    @staticmethod
    def apply_slic_segmentation(
        image_data: np.ndarray,
        num_segments: int = 100,
        compactness: float = 10.0,
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        对影像执行 SLIC 超像素分割

        基于影像光谱与空间信息进行分割，不读取 GeoJSON

        Args:
            image_data: 影像数据数组 (H, W, C)
            num_segments: 超像素数量
            compactness: 紧凑度参数（控制超像素的紧凑程度）

        Returns:
            (分割是否成功, 超像素标签数组, 错误信息或成功消息)
        """
        try:
            if image_data is None or image_data.size == 0:
                return False, None, "影像数据为空"

            # 如果影像有多个波段，使用前三个波段或转换为灰度图
            if image_data.shape[2] >= 3:
                # 使用前三个波段作为 RGB
                rgb_image = image_data[:, :, :3]
                # 确保数据范围在 [0, 1]
                if rgb_image.max() > 1.0:
                    rgb_image = rgb_image / 255.0
            else:
                # 如果只有一个波段，复制三次作为 RGB
                single_band = image_data[:, :, 0]
                if single_band.max() > 1.0:
                    single_band = single_band / 255.0
                rgb_image = np.stack([single_band, single_band, single_band], axis=2)

            # 执行 SLIC 分割
            labels = slic(
                rgb_image,
                n_segments=num_segments,
                compactness=compactness,
                start_label=1,
            )

            logger.info(
                f"SLIC 分割完成: 超像素数量={num_segments}, 紧凑度={compactness}"
            )

            return True, labels, "SLIC 分割成功"

        except Exception as e:
            logger.error(f"SLIC 分割失败: {str(e)}")
            return False, None, f"SLIC 分割失败: {str(e)}"

    @staticmethod
    def extract_superpixel_features(
        image_data: np.ndarray, labels: np.ndarray
    ) -> Tuple[bool, Optional[Dict], str]:
        """
        从超像素区域提取区域级特征

        计算每个超像素区域的光谱均值、方差等特征

        Args:
            image_data: 影像数据数组 (H, W, C)
            labels: 超像素标签数组 (H, W)

        Returns:
            (提取是否成功, 特征字典, 错误信息或成功消息)
        """
        try:
            if image_data is None or labels is None:
                return False, None, "影像数据或标签为空"

            # 获取超像素数量
            num_superpixels = np.max(labels)

            # 初始化特征字典
            features = {
                "num_superpixels": num_superpixels,
                "mean_features": [],
                "std_features": [],
                "superpixel_sizes": [],
            }

            # 为每个超像素计算特征
            for sp_idx in range(1, num_superpixels + 1):
                # 获取该超像素的像素掩码
                mask = labels == sp_idx

                # 计算超像素大小
                sp_size = np.sum(mask)
                features["superpixel_sizes"].append(sp_size)

                # 计算光谱均值
                sp_mean = np.mean(image_data[mask], axis=0)
                features["mean_features"].append(sp_mean)

                # 计算光谱方差
                sp_std = np.std(image_data[mask], axis=0)
                features["std_features"].append(sp_std)

            # 转换为数组
            features["mean_features"] = np.array(features["mean_features"])
            features["std_features"] = np.array(features["std_features"])
            features["superpixel_sizes"] = np.array(features["superpixel_sizes"])

            logger.info(f"超像素特征提取完成: {num_superpixels} 个超像素")

            return True, features, "超像素特征提取成功"

        except Exception as e:
            logger.error(f"超像素特征提取失败: {str(e)}")
            return False, None, f"超像素特征提取失败: {str(e)}"

    @staticmethod
    def label_superpixels_by_points(
        labels: np.ndarray,
        points: List[Tuple[float, float]],
        image_height: int,
        image_width: int,
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        根据病害点位标记超像素为正样本或负样本

        Args:
            labels: 超像素标签数组 (H, W)
            points: 病害木点位列表，每个点为 (x, y) 坐标
            image_height: 影像高度
            image_width: 影像宽度

        Returns:
            (标记是否成功, 样本标签数组, 错误信息或成功消息)
        """
        try:
            if labels is None:
                return False, None, "超像素标签为空"

            # 初始化样本标签数组（0=负样本，1=正样本）
            sample_labels = np.zeros(np.max(labels) + 1, dtype=np.int32)

            # 为每个病害点位标记对应的超像素
            for point_x, point_y in points:
                # 将地理坐标转换为像素坐标
                pixel_x = int(point_x)
                pixel_y = int(point_y)

                # 检查坐标是否在影像范围内
                if 0 <= pixel_x < image_width and 0 <= pixel_y < image_height:
                    # 获取该点所在的超像素标签
                    sp_label = labels[pixel_y, pixel_x]
                    # 标记为正样本
                    sample_labels[sp_label] = 1

            logger.info(
                f"超像素标记完成: 正样本数={np.sum(sample_labels)}, 负样本数={len(sample_labels) - np.sum(sample_labels)}"
            )

            return True, sample_labels, "超像素标记成功"

        except Exception as e:
            logger.error(f"超像素标记失败: {str(e)}")
            return False, None, f"超像素标记失败: {str(e)}"

    @staticmethod
    def extract_superpixel_patches(
        image_data: np.ndarray,
        labels: np.ndarray,
        patch_size: int = 64,
    ) -> Tuple[bool, Optional[List[np.ndarray]], str]:
        """
        从每个超像素区域提取 Patch

        Args:
            image_data: 影像数据数组 (H, W, C)
            labels: 超像素标签数组 (H, W)
            patch_size: Patch 大小

        Returns:
            (提取是否成功, Patch 列表, 错误信息或成功消息)
        """
        try:
            if image_data is None or labels is None:
                return False, None, "影像数据或标签为空"

            patches = []
            num_superpixels = np.max(labels)

            # 为每个超像素提取 Patch
            for sp_idx in range(1, num_superpixels + 1):
                # 获取该超像素的像素坐标
                mask = labels == sp_idx
                coords = np.where(mask)

                if len(coords[0]) == 0:
                    continue

                # 获取超像素的边界框
                min_y, max_y = np.min(coords[0]), np.max(coords[0])
                min_x, max_x = np.min(coords[1]), np.max(coords[1])

                # 计算中心点
                center_y = (min_y + max_y) // 2
                center_x = (min_x + max_x) // 2

                # 提取以中心点为中心的 Patch
                start_y = max(0, center_y - patch_size // 2)
                start_x = max(0, center_x - patch_size // 2)
                end_y = min(image_data.shape[0], start_y + patch_size)
                end_x = min(image_data.shape[1], start_x + patch_size)

                # 调整起始点以确保 Patch 大小一致
                if end_y - start_y < patch_size:
                    start_y = max(0, end_y - patch_size)
                if end_x - start_x < patch_size:
                    start_x = max(0, end_x - patch_size)

                # 提取 Patch
                patch = image_data[start_y:end_y, start_x:end_x, :]

                # 如果 Patch 大小不足，进行填充
                if patch.shape[0] < patch_size or patch.shape[1] < patch_size:
                    padded_patch = np.zeros(
                        (patch_size, patch_size, image_data.shape[2]),
                        dtype=image_data.dtype,
                    )
                    padded_patch[: patch.shape[0], : patch.shape[1], :] = patch
                    patch = padded_patch

                patches.append(patch)

            logger.info(f"Patch 提取完成: {len(patches)} 个 Patch")

            return True, patches, "Patch 提取成功"

        except Exception as e:
            logger.error(f"Patch 提取失败: {str(e)}")
            return False, None, f"Patch 提取失败: {str(e)}"

    @staticmethod
    def merge_superpixel_results(
        superpixel_labels_list: List[np.ndarray],
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        合并多个影像块的超像素分割结果

        为每个影像块维护独立的超像素编号空间

        Args:
            superpixel_labels_list: 超像素标签数组列表

        Returns:
            (合并是否成功, 合并后的标签数组, 错误信息或成功消息)
        """
        try:
            if not superpixel_labels_list:
                return False, None, "超像素标签列表为空"

            # 初始化合并后的标签数组
            merged_labels = superpixel_labels_list[0].copy()
            current_max_label = np.max(merged_labels)

            # 合并后续的标签数组
            for labels in superpixel_labels_list[1:]:
                # 重新编号标签以避免冲突
                relabeled = labels.copy()
                relabeled[relabeled > 0] += current_max_label

                # 合并标签数组
                merged_labels = np.maximum(merged_labels, relabeled)
                current_max_label = np.max(merged_labels)

            logger.info(f"超像素结果合并完成: 总超像素数={current_max_label}")

            return True, merged_labels, "超像素结果合并成功"

        except Exception as e:
            logger.error(f"超像素结果合并失败: {str(e)}")
            return False, None, f"超像素结果合并失败: {str(e)}"
