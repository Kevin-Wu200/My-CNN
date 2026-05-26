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
    def crop_patches_from_files(
        image_paths: List[str],
        points: List[Dict],
        patch_size: int = 64,
    ) -> Tuple[bool, Optional[List[np.ndarray]], str]:
        """
        基于磁盘文件的流式 Patch 裁剪（适用于大型遥感影像）。

        不将完整影像加载到内存，而是通过 read_image_chunk 按需读取每个 Patch 区域。
        支持多时相影像：为每个点位在所有时相影像中同步裁剪对应区域。

        Args:
            image_paths: 多时相影像文件路径列表
            points: 病害木点位列表
            patch_size: 裁剪 Patch 的大小

        Returns:
            (裁剪是否成功, 裁剪后的 Patch 列表, 错误信息或成功消息)
        """
        try:
            patches = list(SampleConstructionService.stream_patches_from_files(
                image_paths, points, patch_size
            ))
            logger.info(f"已从文件流式裁剪 {len(patches)} 个多时相 Patch (patch_size={patch_size})")
            return True, patches, "流式 Patch 裁剪成功"
        except Exception as e:
            logger.error(f"流式 Patch 裁剪失败: {str(e)}")
            return False, None, f"流式 Patch 裁剪失败: {str(e)}"

    @staticmethod
    def stream_patches_from_files(
        image_paths: List[str],
        points: List[Dict],
        patch_size: int = 64,
        batch_size: int = 256,
    ):
        """
        流式生成器：按批次从磁盘裁剪 Patch 并逐批 yield。

        与 crop_patches_from_files 功能相同，但使用生成器模式：
        - 每处理 batch_size 个点位就 yield 一批 Patch
        - 支持流式消费，训练器可边生成边训练，避免 OOM

        Yields:
            List[np.ndarray]: 一批多时相 Patch 列表，每个 Patch 形状为 (T, H, W, C)
        """
        if not image_paths or not points:
            return

        # 预加载所有影像信息以验证范围（仅获取元数据，不加载像素数据）
        img_infos = []
        for img_path in image_paths:
            success_info, info, _ = ImageReader.get_image_info(img_path)
            if not success_info:
                raise ValueError(f"获取影像信息失败: {img_path}")
            img_infos.append(info)

        batch = []
        for point_idx, point in enumerate(points):
            point_x = int(point["x"])
            point_y = int(point["y"])

            # 计算裁剪区域
            start_x = max(0, point_x - patch_size // 2)
            start_y = max(0, point_y - patch_size // 2)
            end_x = start_x + patch_size
            end_y = start_y + patch_size

            temporal_patches = []
            for idx, img_path in enumerate(image_paths):
                info = img_infos[idx]
                img_w = info["width"]
                img_h = info["height"]

                # 边界调整
                adj_start_x = max(0, start_x)
                adj_start_y = max(0, start_y)
                adj_end_x = min(img_w, end_x)
                adj_end_y = min(img_h, end_y)

                read_w = adj_end_x - adj_start_x
                read_h = adj_end_y - adj_start_y
                if read_w <= 0 or read_h <= 0:
                    raise ValueError(f"点位 {point_idx} 超出影像范围")

                success, chunk, msg = ImageReader.read_image_chunk(
                    img_path,
                    adj_start_x, adj_start_y,
                    read_w, read_h,
                )
                if not success:
                    raise RuntimeError(f"读取影像块失败: {msg}")

                # 如果 Patch 大小不足，进行填充
                if chunk.shape[0] < patch_size or chunk.shape[1] < patch_size:
                    padded_patch = np.zeros(
                        (patch_size, patch_size, chunk.shape[2]),
                        dtype=chunk.dtype,
                    )
                    padded_patch[: chunk.shape[0], : chunk.shape[1], :] = chunk
                    chunk = padded_patch

                temporal_patches.append(chunk)

            # 将多时相 Patch 堆叠为 (T, H, W, C) 格式
            temporal_patch_stack = np.stack(temporal_patches, axis=0)
            batch.append(temporal_patch_stack)

            # 达到批次大小时 yield
            if len(batch) >= batch_size:
                yield batch
                batch = []

        # yield 剩余的
        if batch:
            yield batch

    @staticmethod
    def stream_sample_batches(
        image_paths: List[str],
        positive_points: List[Dict],
        negative_points: Optional[List[Dict]] = None,
        patch_size: int = 64,
        batch_size: int = 256,
        num_negative_samples: int = 0,
        min_distance: int = 100,
    ):
        """
        流式训练样本生成器：逐批 yield (patches, labels) 元组供训练器消费。

        整合正负样本的流式生成，每批返回 patches 数组和对应的 labels 数组。

        Args:
            image_paths: 多时相影像文件路径列表
            positive_points: 正样本点位
            negative_points: 预定义的负样本点位（可选）
            patch_size: Patch 大小
            batch_size: 每批样本数
            num_negative_samples: 自动生成的负样本数量
            min_distance: 负样本与正样本的最小距离

        Yields:
            Tuple[np.ndarray, np.ndarray]: (patches 批次, labels 批次)
        """
        if positive_points:
            pos_patches = []
            pos_labels = []
            for batch_patches in SampleConstructionService.stream_patches_from_files(
                image_paths, positive_points, patch_size, batch_size
            ):
                # 交错正负样本输出
                yield np.array(batch_patches), np.ones(len(batch_patches), dtype=np.int64)
            del pos_patches, pos_labels

        if negative_points:
            for batch_patches in SampleConstructionService.stream_patches_from_files(
                image_paths, negative_points, patch_size, batch_size
            ):
                yield np.array(batch_patches), np.zeros(len(batch_patches), dtype=np.int64)

    @staticmethod
    def generate_negative_samples_from_files(
        image_paths: List[str],
        positive_points: List[Dict],
        num_negative_samples: int = 100,
        patch_size: int = 64,
        min_distance: int = 100,
    ) -> Tuple[bool, Optional[List[np.ndarray]], str]:
        """
        基于磁盘文件的流式负样本生成（适用于大型遥感影像）。

        不将完整影像加载到内存，通过 read_image_chunk 按需读取随机点位的 Patch 区域。

        Args:
            image_paths: 多时相影像文件路径列表
            positive_points: 正样本点位列表
            num_negative_samples: 要生成的负样本数量
            patch_size: Patch 大小
            min_distance: 负样本与正样本的最小距离

        Returns:
            (生成是否成功, 负样本 Patch 列表, 错误信息或成功消息)
        """
        try:
            if not image_paths:
                return False, None, "影像路径列表为空"

            # 获取第一个影像的信息以确定有效范围
            success_info, info, msg = ImageReader.get_image_info(image_paths[0])
            if not success_info:
                return False, None, f"获取影像信息失败: {msg}"

            image_width = info["width"]
            image_height = info["height"]

            negative_patches = []
            attempts = 0
            max_attempts = num_negative_samples * 10

            while len(negative_patches) < num_negative_samples and attempts < max_attempts:
                attempts += 1

                # 随机生成点位
                random_x = np.random.randint(patch_size // 2, max(patch_size // 2 + 1, image_width - patch_size // 2))
                random_y = np.random.randint(patch_size // 2, max(patch_size // 2 + 1, image_height - patch_size // 2))

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

                # 计算裁剪区域
                start_x = random_x - patch_size // 2
                start_y = random_y - patch_size // 2

                # 从所有时相影像中按需读取对应区域
                temporal_patches = []
                for img_path in image_paths:
                    success, chunk, chunk_msg = ImageReader.read_image_chunk(
                        img_path,
                        start_x, start_y,
                        patch_size, patch_size,
                    )
                    if not success:
                        # 如果读取失败，跳过这个点位
                        logger.debug(f"读取块失败: {chunk_msg}")
                        break

                    temporal_patches.append(chunk)

                if len(temporal_patches) == len(image_paths):
                    # 将多时相 Patch 堆叠
                    temporal_patch_stack = np.stack(temporal_patches, axis=0)
                    negative_patches.append(temporal_patch_stack)

                if len(negative_patches) > 0 and len(negative_patches) % max(1, num_negative_samples // 5) == 0:
                    logger.info(f"流式负样本生成进度: {len(negative_patches)}/{num_negative_samples}")

            logger.info(f"已从文件流式生成 {len(negative_patches)} 个负样本")

            return True, negative_patches, "流式负样本生成成功"

        except Exception as e:
            logger.error(f"流式负样本生成失败: {str(e)}")
            return False, None, f"流式负样本生成失败: {str(e)}"

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
