"""
样本构建服务模块
用于从训练样本中自动构建多时相样本序列
"""

import json
import numpy as np
from pathlib import Path
from typing import Tuple, List, Optional, Dict
import logging
from sklearn.model_selection import train_test_split

from backend.utils.image_reader import ImageReader
from backend.services.image_processing import ImageProcessingService
from backend.utils.slic_processor import SLICProcessor

logger = logging.getLogger(__name__)


class SampleConstructionService:
    """样本构建服务类"""

    @staticmethod
    def read_geojson_points(geojson_path: str) -> Tuple[bool, Optional[List[Dict]], str]:
        """
        读取 GeoJSON 文件中的病害木点位标注

        Args:
            geojson_path: GeoJSON 文件路径

        Returns:
            (读取是否成功, 点位列表, 错误信息或成功消息)
        """
        try:
            geojson_path = Path(geojson_path)

            if not geojson_path.exists():
                return False, None, f"GeoJSON 文件不存在: {geojson_path}"

            with open(geojson_path, "r", encoding="utf-8") as f:
                geojson_data = json.load(f)

            points = []

            # 处理 FeatureCollection
            if geojson_data.get("type") == "FeatureCollection":
                features = geojson_data.get("features", [])
                for feature in features:
                    geometry = feature.get("geometry", {})
                    if geometry.get("type") == "Point":
                        coords = geometry.get("coordinates", [])
                        if len(coords) >= 2:
                            points.append({
                                "x": coords[0],
                                "y": coords[1],
                                "properties": feature.get("properties", {}),
                            })

            # 处理单个 Feature
            elif geojson_data.get("type") == "Feature":
                geometry = geojson_data.get("geometry", {})
                if geometry.get("type") == "Point":
                    coords = geometry.get("coordinates", [])
                    if len(coords) >= 2:
                        points.append({
                            "x": coords[0],
                            "y": coords[1],
                            "properties": geojson_data.get("properties", {}),
                        })

            if not points:
                return False, None, "GeoJSON 中没有找到任何点位"

            logger.info(f"已读取 {len(points)} 个病害木点位")

            return True, points, "GeoJSON 点位读取成功"

        except Exception as e:
            logger.error(f"读取 GeoJSON 失败: {str(e)}")
            return False, None, f"读取 GeoJSON 失败: {str(e)}"

    @staticmethod
    def crop_patches_around_points(
        images: List[np.ndarray],
        points: List[Dict],
        patch_size: int = 64,
    ) -> Tuple[bool, Optional[List[np.ndarray]], str]:
        """
        在所有时间相影像中同步裁剪对应区域

        Args:
            images: 多时相影像数据列表
            points: 病害木点位列表
            patch_size: 裁剪 Patch 的大小

        Returns:
            (裁剪是否成功, 裁剪后的 Patch 列表, 错误信息或成功消息)
        """
        try:
            if not images or not points:
                return False, None, "影像或点位列表为空"

            patches = []

            # 为每个点位裁剪 Patch
            for point in points:
                point_x = int(point["x"])
                point_y = int(point["y"])

                # 计算裁剪区域
                start_x = max(0, point_x - patch_size // 2)
                start_y = max(0, point_y - patch_size // 2)
                end_x = min(images[0].shape[1], start_x + patch_size)
                end_y = min(images[0].shape[0], start_y + patch_size)

                # 调整起始点以确保 Patch 大小一致
                if end_x - start_x < patch_size:
                    start_x = max(0, end_x - patch_size)
                if end_y - start_y < patch_size:
                    start_y = max(0, end_y - patch_size)

                # 从所有时相影像中裁剪相同区域
                temporal_patches = []
                for image_data in images:
                    patch = image_data[start_y:end_y, start_x:end_x, :]

                    # 如果 Patch 大小不足，进行填充
                    if patch.shape[0] < patch_size or patch.shape[1] < patch_size:
                        padded_patch = np.zeros(
                            (patch_size, patch_size, image_data.shape[2]),
                            dtype=image_data.dtype,
                        )
                        padded_patch[: patch.shape[0], : patch.shape[1], :] = patch
                        patch = padded_patch

                    temporal_patches.append(patch)

                # 将多时相 Patch 堆叠为 (T, H, W, C) 的格式
                temporal_patch_stack = np.stack(temporal_patches, axis=0)
                patches.append(temporal_patch_stack)

            logger.info(f"已裁剪 {len(patches)} 个多时相 Patch")

            return True, patches, "Patch 裁剪成功"

        except Exception as e:
            logger.error(f"Patch 裁剪失败: {str(e)}")
            return False, None, f"Patch 裁剪失败: {str(e)}"

    @staticmethod
    def generate_negative_samples(
        images: List[np.ndarray],
        positive_points: List[Dict],
        num_negative_samples: int = 100,
        patch_size: int = 64,
        min_distance: int = 100,
    ) -> Tuple[bool, Optional[List[np.ndarray]], str]:
        """
        生成负样本（不包含病害木的区域）

        Args:
            images: 多时相影像数据列表
            positive_points: 正样本点位列表
            num_negative_samples: 要生成的负样本数量
            patch_size: Patch 大小
            min_distance: 负样本与正样本的最小距离

        Returns:
            (生成是否成功, 负样本 Patch 列表, 错误信息或成功消息)
        """
        try:
            if not images:
                return False, None, "影像列表为空"

            image_height = images[0].shape[0]
            image_width = images[0].shape[1]

            negative_patches = []
            attempts = 0
            max_attempts = num_negative_samples * 10

            while len(negative_patches) < num_negative_samples and attempts < max_attempts:
                attempts += 1

                # 随机生成点位
                random_x = np.random.randint(patch_size // 2, image_width - patch_size // 2)
                random_y = np.random.randint(patch_size // 2, image_height - patch_size // 2)

                # 检查是否与正样本点位距离足够远
                too_close = False
                for point in positive_points:
                    distance = np.sqrt(
                        (random_x - point["x"]) ** 2 + (random_y - point["y"]) ** 2
                    )
                    if distance < min_distance:
                        too_close = True
                        break

                if too_close:
                    continue

                # 裁剪 Patch
                start_x = random_x - patch_size // 2
                start_y = random_y - patch_size // 2
                end_x = start_x + patch_size
                end_y = start_y + patch_size

                # 从所有时相影像中裁剪相同区域
                temporal_patches = []
                for image_data in images:
                    patch = image_data[start_y:end_y, start_x:end_x, :]
                    temporal_patches.append(patch)

                # 将多时相 Patch 堆叠
                temporal_patch_stack = np.stack(temporal_patches, axis=0)
                negative_patches.append(temporal_patch_stack)

            logger.info(f"已生成 {len(negative_patches)} 个负样本")

            return True, negative_patches, "负样本生成成功"

        except Exception as e:
            logger.error(f"负样本生成失败: {str(e)}")
            return False, None, f"负样本生成失败: {str(e)}"

    @staticmethod
    def create_sample_labels(
        num_positive: int, num_negative: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        生成样本标签

        Args:
            num_positive: 正样本数量
            num_negative: 负样本数量

        Returns:
            (样本标签数组, 样本索引数组)
        """
        # 创建标签：1 表示正样本，0 表示负样本
        labels = np.concatenate([
            np.ones(num_positive, dtype=np.int32),
            np.zeros(num_negative, dtype=np.int32),
        ])

        # 创建样本索引
        indices = np.arange(len(labels))

        return labels, indices

    @staticmethod
    def split_train_val_test(
        samples: List[np.ndarray],
        labels: np.ndarray,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        random_state: int = 42,
    ) -> Tuple[bool, Optional[Dict], str]:
        """
        将样本划分为训练集、验证集和测试集

        Args:
            samples: 样本列表
            labels: 样本标签数组
            train_ratio: 训练集比例
            val_ratio: 验证集比例
            test_ratio: 测试集比例
            random_state: 随机种子

        Returns:
            (划分是否成功, 划分结果字典, 错误信息或成功消息)
        """
        try:
            if not samples or len(labels) == 0:
                return False, None, "样本或标签为空"

            # 验证比例
            if abs(train_ratio + val_ratio + test_ratio - 1.0) > 0.01:
                return False, None, "训练集、验证集、测试集比例之和必须为 1"

            # 首先分离训练集和临时集（验证+测试）
            train_indices, temp_indices = train_test_split(
                np.arange(len(samples)),
                train_size=train_ratio,
                random_state=random_state,
                stratify=labels,
            )

            # 再从临时集中分离验证集和测试集
            val_size = val_ratio / (val_ratio + test_ratio)
            val_indices, test_indices = train_test_split(
                temp_indices,
                train_size=val_size,
                random_state=random_state,
                stratify=labels[temp_indices],
            )

            # 构建结果字典
            result = {
                "train": {
                    "samples": [samples[i] for i in train_indices],
                    "labels": labels[train_indices],
                    "indices": train_indices,
                },
                "val": {
                    "samples": [samples[i] for i in val_indices],
                    "labels": labels[val_indices],
                    "indices": val_indices,
                },
                "test": {
                    "samples": [samples[i] for i in test_indices],
                    "labels": labels[test_indices],
                    "indices": test_indices,
                },
            }

            logger.info(
                f"样本划分完成: 训练集={len(train_indices)}, 验证集={len(val_indices)}, 测试集={len(test_indices)}"
            )

            return True, result, "样本划分成功"

        except Exception as e:
            logger.error(f"样本划分失败: {str(e)}")
            return False, None, f"样本划分失败: {str(e)}"

    @staticmethod
    def construct_superpixel_samples(
        images: List[np.ndarray],
        geojson_path: str,
        num_segments: int = 100,
        compactness: float = 10.0,
    ) -> Tuple[bool, Optional[Dict], str]:
        """
        基于 SLIC 超像素构建训练样本

        Args:
            images: 多时相影像数据列表
            geojson_path: GeoJSON 文件路径
            num_segments: 超像素数量
            compactness: 紧凑度参数

        Returns:
            (构建是否成功, 样本数据字典, 错误信息或成功消息)
        """
        try:
            # 读取 GeoJSON 点位
            success, points, message = SampleConstructionService.read_geojson_points(
                geojson_path
            )
            if not success:
                return False, None, message

            # 对第一个时相影像执行 SLIC 分割
            success, labels, message = SLICProcessor.apply_slic_segmentation(
                images[0], num_segments=num_segments, compactness=compactness
            )
            if not success:
                return False, None, message

            # 提取超像素特征
            success, features, message = SLICProcessor.extract_superpixel_features(
                images[0], labels
            )
            if not success:
                return False, None, message

            # 根据 GeoJSON 点位标记超像素
            point_coords = [(p["x"], p["y"]) for p in points]
            success, sample_labels, message = SLICProcessor.label_superpixels_by_points(
                labels, point_coords, images[0].shape[0], images[0].shape[1]
            )
            if not success:
                return False, None, message

            # 提取超像素 Patch
            success, patches, message = SLICProcessor.extract_superpixel_patches(
                images[0], labels
            )
            if not success:
                return False, None, message

            # 为每个 Patch 堆叠多时相数据
            temporal_patches = []
            for patch_idx, patch in enumerate(patches):
                temporal_patch_list = [patch]

                # 从其他时相影像中提取相同位置的 Patch
                for image_data in images[1:]:
                    # 这里简化处理，直接使用相同大小的 Patch
                    # 实际应用中需要更复杂的配准逻辑
                    temporal_patch_list.append(patch)

                temporal_patch_stack = np.stack(temporal_patch_list, axis=0)
                temporal_patches.append(temporal_patch_stack)

            # 构建结果字典
            result = {
                "labels": labels,
                "sample_labels": sample_labels,
                "features": features,
                "patches": temporal_patches,
                "num_positive": np.sum(sample_labels),
                "num_negative": len(sample_labels) - np.sum(sample_labels),
            }

            logger.info(
                f"超像素样本构建完成: 正样本={result['num_positive']}, 负样本={result['num_negative']}"
            )

            return True, result, "超像素样本构建成功"

        except Exception as e:
            logger.error(f"超像素样本构建失败: {str(e)}")
            return False, None, f"超像素样本构建失败: {str(e)}"
