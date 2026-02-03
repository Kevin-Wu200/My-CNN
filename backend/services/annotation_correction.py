"""
标注修正服务模块
用于处理检测结果的导出、修正和回流
"""

import json
import numpy as np
from pathlib import Path
from typing import Tuple, Optional, List, Dict
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class AnnotationCorrectionService:
    """标注修正服务类"""

    @staticmethod
    def export_detections_to_geojson(
        points: List[Dict],
        output_path: str,
        image_width: int,
        image_height: int,
        metadata: Optional[Dict] = None,
    ) -> Tuple[bool, str]:
        """
        将检测结果导出为 GeoJSON 文件

        Args:
            points: 检测点位列表
            output_path: 输出文件路径
            image_width: 影像宽度
            image_height: 影像高度
            metadata: 元数据字典

        Returns:
            (导出是否成功, 错误信息或成功消息)
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # 构建 GeoJSON 特征集合
            features = []

            for point in points:
                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [point["x"], point["y"]],
                    },
                    "properties": {
                        "confidence": point.get("confidence", 0.0),
                        "superpixel_id": point.get("superpixel_id", -1),
                        "cluster_size": point.get("cluster_size", 1),
                    },
                }
                features.append(feature)

            # 构建 GeoJSON FeatureCollection
            geojson_data = {
                "type": "FeatureCollection",
                "features": features,
                "properties": {
                    "image_width": image_width,
                    "image_height": image_height,
                    "total_points": len(points),
                    "export_time": datetime.now().isoformat(),
                },
            }

            # 添加元数据
            if metadata:
                geojson_data["properties"].update(metadata)

            # 写入文件
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(geojson_data, f, indent=2, ensure_ascii=False)

            logger.info(f"检测结果已导出为 GeoJSON: {output_path}")

            return True, f"导出成功: {len(points)} 个点位"

        except Exception as e:
            logger.error(f"导出 GeoJSON 失败: {str(e)}")
            return False, f"导出失败: {str(e)}"

    @staticmethod
    def import_corrected_geojson(
        geojson_path: str,
    ) -> Tuple[bool, Optional[List[Dict]], str]:
        """
        导入修正后的 GeoJSON 文件

        Args:
            geojson_path: GeoJSON 文件路径

        Returns:
            (导入是否成功, 修正后的点位列表, 错误信息或成功消息)
        """
        try:
            geojson_path = Path(geojson_path)

            if not geojson_path.exists():
                return False, None, f"GeoJSON 文件不存在: {geojson_path}"

            with open(geojson_path, "r", encoding="utf-8") as f:
                geojson_data = json.load(f)

            # 验证 GeoJSON 格式
            if geojson_data.get("type") != "FeatureCollection":
                return False, None, "GeoJSON 必须是 FeatureCollection 类型"

            features = geojson_data.get("features", [])
            if not features:
                return False, None, "GeoJSON 中没有任何特征"

            # 提取点位
            points = []
            for feature in features:
                geometry = feature.get("geometry", {})
                if geometry.get("type") != "Point":
                    continue

                coords = geometry.get("coordinates", [])
                if len(coords) < 2:
                    continue

                properties = feature.get("properties", {})

                point = {
                    "x": coords[0],
                    "y": coords[1],
                    "confidence": properties.get("confidence", 1.0),
                    "properties": properties,
                }
                points.append(point)

            logger.info(f"已导入 {len(points)} 个修正后的点位")

            return True, points, "导入成功"

        except json.JSONDecodeError as e:
            logger.error(f"GeoJSON 格式错误: {str(e)}")
            return False, None, f"GeoJSON 格式错误: {str(e)}"
        except Exception as e:
            logger.error(f"导入 GeoJSON 失败: {str(e)}")
            return False, None, f"导入失败: {str(e)}"

    @staticmethod
    def validate_corrected_annotations(
        points: List[Dict],
        image_width: int,
        image_height: int,
    ) -> Tuple[bool, List[str]]:
        """
        验证修正后的标注数据

        Args:
            points: 点位列表
            image_width: 影像宽度
            image_height: 影像高度

        Returns:
            (验证是否通过, 错误信息列表)
        """
        errors = []

        if not points:
            errors.append("点位列表为空")
            return False, errors

        for i, point in enumerate(points):
            # 检查必要字段
            if "x" not in point or "y" not in point:
                errors.append(f"点位 {i} 缺少坐标信息")
                continue

            # 检查坐标范围
            if not (0 <= point["x"] < image_width):
                errors.append(
                    f"点位 {i} 的 X 坐标超出范围: {point['x']} (有效范围: 0-{image_width})"
                )

            if not (0 <= point["y"] < image_height):
                errors.append(
                    f"点位 {i} 的 Y 坐标超出范围: {point['y']} (有效范围: 0-{image_height})"
                )

            # 检查置信度
            if "confidence" in point:
                if not (0 <= point["confidence"] <= 1):
                    errors.append(
                        f"点位 {i} 的置信度无效: {point['confidence']} (有效范围: 0-1)"
                    )

        if errors:
            return False, errors

        return True, []

    @staticmethod
    def merge_original_and_corrected(
        original_points: List[Dict],
        corrected_points: List[Dict],
        merge_distance: int = 50,
    ) -> List[Dict]:
        """
        合并原始检测结果和修正后的标注

        Args:
            original_points: 原始检测点位列表
            corrected_points: 修正后的点位列表
            merge_distance: 合并距离阈值

        Returns:
            合并后的点位列表
        """
        merged_points = []
        used_corrected = set()

        # 首先处理原始点位
        for orig_point in original_points:
            # 查找对应的修正点位
            matched_corrected = None
            matched_idx = -1

            for j, corr_point in enumerate(corrected_points):
                if j in used_corrected:
                    continue

                distance = np.sqrt(
                    (orig_point["x"] - corr_point["x"]) ** 2
                    + (orig_point["y"] - corr_point["y"]) ** 2
                )

                if distance <= merge_distance:
                    matched_corrected = corr_point
                    matched_idx = j
                    break

            if matched_corrected:
                # 使用修正后的坐标
                merged_points.append(matched_corrected)
                used_corrected.add(matched_idx)
            else:
                # 保留原始点位
                merged_points.append(orig_point)

        # 添加未匹配的修正点位
        for j, corr_point in enumerate(corrected_points):
            if j not in used_corrected:
                merged_points.append(corr_point)

        logger.info(
            f"标注合并完成: 原始={len(original_points)}, "
            f"修正={len(corrected_points)}, 合并后={len(merged_points)}"
        )

        return merged_points

    @staticmethod
    def create_training_samples_from_annotations(
        image_data: np.ndarray,
        points: List[Dict],
        patch_size: int = 64,
    ) -> Tuple[bool, Optional[List[np.ndarray]], Optional[np.ndarray], str]:
        """
        从修正后的标注创建训练样本

        Args:
            image_data: 影像数据
            points: 点位列表
            patch_size: Patch 大小

        Returns:
            (创建是否成功, Patch 列表, 标签数组, 错误信息或成功消息)
        """
        try:
            if image_data is None or not points:
                return False, None, None, "影像数据或点位列表为空"

            patches = []
            labels = []

            for point in points:
                point_x = int(point["x"])
                point_y = int(point["y"])

                # 计算裁剪区域
                start_x = max(0, point_x - patch_size // 2)
                start_y = max(0, point_y - patch_size // 2)
                end_x = min(image_data.shape[1], start_x + patch_size)
                end_y = min(image_data.shape[0], start_y + patch_size)

                # 调整起始点以确保 Patch 大小一致
                if end_x - start_x < patch_size:
                    start_x = max(0, end_x - patch_size)
                if end_y - start_y < patch_size:
                    start_y = max(0, end_y - patch_size)

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
                # 修正后的标注都是正样本
                labels.append(1)

            labels = np.array(labels, dtype=np.int32)

            logger.info(f"已创建 {len(patches)} 个训练样本")

            return True, patches, labels, "训练样本创建成功"

        except Exception as e:
            logger.error(f"训练样本创建失败: {str(e)}")
            return False, None, None, f"训练样本创建失败: {str(e)}"
