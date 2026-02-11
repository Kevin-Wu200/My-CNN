"""
病害木检测服务模块
用于对待检测影像进行病害木检测

支持统一的 1024×1024 分块处理和并行处理
"""

import torch
import torch.nn as nn
import numpy as np
from typing import Tuple, Optional, List, Dict
import logging

from backend.utils.slic_processor import SLICProcessor
from backend.utils.tile_utils import TilingService, Tile, DEFAULT_TILE_SIZE
from backend.services.parallel_processing import ParallelProcessingService

logger = logging.getLogger(__name__)


# 模块级别的瓦片处理函数，用于多进程处理（必须在模块级别以支持pickle序列化）
def _process_tile_for_parallel(args):
    """
    处理单个瓦片的模块级别函数

    Args:
        args: 包含 (service, tile) 的元组

    Returns:
        处理结果字典或错误字典
    """
    service, tile = args
    try:
        success, result, msg = service._process_single_tile(tile)
        if not success:
            return {"error": msg, "tile_index": tile.tile_index}
        return result
    except Exception as e:
        logger.error(f"瓦片 {tile.tile_index} 处理异常: {str(e)}")
        return {"error": str(e), "tile_index": tile.tile_index}


class DiseaseTreeDetectionService:
    """病害木检测服务类"""

    def __init__(
        self,
        model: nn.Module,
        device: str = "cpu",
        confidence_threshold: float = 0.5,
    ):
        """
        初始化检测服务

        Args:
            model: 训练完成的模型
            device: 计算设备
            confidence_threshold: 置信度阈值
        """
        self.model = model.to(device)
        self.device = device
        self.confidence_threshold = confidence_threshold
        self.model.eval()

    def detect_on_image(
        self,
        image_data: np.ndarray,
    ) -> Tuple[bool, Optional[Dict], str]:
        """
        对单个影像进行病害木检测

        Args:
            image_data: 影像数据 (H, W, C)

        Returns:
            (检测是否成功, 检测结果字典, 错误信息或成功消息)
        """
        try:
            if image_data is None or image_data.size == 0:
                return False, None, "影像数据为空"

            # 执行 SLIC 超像素分割
            success, labels, message = SLICProcessor.apply_slic_segmentation(
                image_data
            )
            if not success:
                return False, None, message

            # 提取超像素 Patch
            success, patches, message = SLICProcessor.extract_superpixel_patches(
                image_data, labels
            )
            if not success:
                return False, None, message

            # 对每个 Patch 进行检测
            detections = []
            confidences = []

            with torch.no_grad():
                for patch in patches:
                    # 转换为张量
                    patch_tensor = torch.from_numpy(patch).float()
                    patch_tensor = patch_tensor.permute(2, 0, 1).unsqueeze(0)
                    patch_tensor = patch_tensor.to(self.device)

                    # 模型推理
                    output = self.model(patch_tensor)
                    probabilities = torch.softmax(output, dim=1)

                    # 获取预测类别和置信度
                    confidence, predicted_class = torch.max(probabilities, 1)

                    detections.append(predicted_class.item())
                    confidences.append(confidence.item())

            # 构建检测结果
            result = {
                "labels": labels,
                "detections": np.array(detections),
                "confidences": np.array(confidences),
                "num_superpixels": len(patches),
                "num_positive": np.sum(np.array(detections) == 1),
            }

            logger.info(
                f"检测完成: 总超像素数={result['num_superpixels']}, "
                f"病害木超像素数={result['num_positive']}"
            )

            return True, result, "检测成功"

        except Exception as e:
            logger.error(f"检测失败: {str(e)}")
            return False, None, f"检测失败: {str(e)}"

    def detect_on_multitemporal_images(
        self,
        images: List[np.ndarray],
    ) -> Tuple[bool, Optional[Dict], str]:
        """
        对多时相影像进行病害木检测

        Args:
            images: 多时相影像数据列表

        Returns:
            (检测是否成功, 检测结果字典, 错误信息或成功消息)
        """
        try:
            if not images or len(images) == 0:
                return False, None, "影像列表为空"

            # 对每个时相进行检测
            all_results = []

            for t, image_data in enumerate(images):
                logger.info(f"检测第 {t + 1} 个时相影像")

                success, result, message = self.detect_on_image(image_data)
                if not success:
                    return False, None, message

                all_results.append(result)

            # 合并结果
            merged_result = {
                "num_timesteps": len(images),
                "results_per_timestep": all_results,
                "consensus_detections": self._compute_consensus_detections(
                    all_results
                ),
            }

            logger.info(f"多时相检测完成: {len(images)} 个时相")

            return True, merged_result, "多时相检测成功"

        except Exception as e:
            logger.error(f"多时相检测失败: {str(e)}")
            return False, None, f"多时相检测失败: {str(e)}"

    def _compute_consensus_detections(
        self,
        results: List[Dict],
    ) -> np.ndarray:
        """
        计算多时相检测的共识结果

        Args:
            results: 多个时相的检测结果列表

        Returns:
            共识检测结果
        """
        # 计算每个超像素在所有时相中被检测为病害木的次数
        num_superpixels = results[0]["num_superpixels"]
        consensus_scores = np.zeros(num_superpixels)

        for result in results:
            consensus_scores += result["detections"]

        # 计算共识（超过一半的时相检测为病害木）
        consensus_threshold = len(results) / 2
        consensus_detections = (consensus_scores > consensus_threshold).astype(np.int32)

        return consensus_detections

    def extract_detection_coordinates(
        self,
        labels: np.ndarray,
        detections: np.ndarray,
        confidences: np.ndarray,
    ) -> Tuple[bool, Optional[List[Dict]], str]:
        """
        从检测结果中提取病害木点位坐标

        Args:
            labels: 超像素标签数组
            detections: 检测结果数组
            confidences: 置信度数组

        Returns:
            (提取是否成功, 点位列表, 错误信息或成功消息)
        """
        try:
            if labels is None or detections is None:
                return False, None, "标签或检测结果为空"

            points = []

            # 为每个被检测为病害木的超像素提取中心点
            for sp_idx in range(1, np.max(labels) + 1):
                if detections[sp_idx - 1] == 1:
                    # 获取该超像素的像素坐标
                    mask = labels == sp_idx
                    coords = np.where(mask)

                    if len(coords[0]) > 0:
                        # 计算中心点
                        center_y = int(np.mean(coords[0]))
                        center_x = int(np.mean(coords[1]))

                        # 获取置信度
                        confidence = confidences[sp_idx - 1]

                        # 只保留置信度高于阈值的点位
                        if confidence >= self.confidence_threshold:
                            points.append({
                                "x": center_x,
                                "y": center_y,
                                "confidence": float(confidence),
                                "superpixel_id": int(sp_idx),
                            })

            logger.info(f"已提取 {len(points)} 个病害木点位")

            return True, points, "点位提取成功"

        except Exception as e:
            logger.error(f"点位提取失败: {str(e)}")
            return False, None, f"点位提取失败: {str(e)}"

    def _process_single_tile(
        self,
        tile: Tile,
    ) -> Tuple[bool, Optional[Dict], str]:
        """
        处理单个分块

        Args:
            tile: Tile 对象

        Returns:
            (处理是否成功, 处理结果字典, 错误信息或成功消息)
        """
        try:
            tile_data = tile.data

            # 执行 SLIC 超像素分割
            success, labels, message = SLICProcessor.apply_slic_segmentation(
                tile_data
            )
            if not success:
                return False, None, message

            # 提取超像素 Patch
            success, patches, message = SLICProcessor.extract_superpixel_patches(
                tile_data, labels
            )
            if not success:
                return False, None, message

            # 对每个 Patch 进行检测
            detections = []
            confidences = []

            with torch.no_grad():
                for patch in patches:
                    # 转换为张量
                    patch_tensor = torch.from_numpy(patch).float()
                    patch_tensor = patch_tensor.permute(2, 0, 1).unsqueeze(0)
                    patch_tensor = patch_tensor.to(self.device)

                    # 模型推理
                    output = self.model(patch_tensor)
                    probabilities = torch.softmax(output, dim=1)

                    # 获取预测类别和置信度
                    confidence, predicted_class = torch.max(probabilities, 1)

                    detections.append(predicted_class.item())
                    confidences.append(confidence.item())

            # 提取检测坐标
            points = []
            for sp_idx in range(1, np.max(labels) + 1):
                if detections[sp_idx - 1] == 1:
                    # 获取该超像素的像素坐标
                    mask = labels == sp_idx
                    coords = np.where(mask)

                    if len(coords[0]) > 0:
                        # 计算中心点
                        center_y = int(np.mean(coords[0]))
                        center_x = int(np.mean(coords[1]))

                        # 获取置信度
                        confidence = confidences[sp_idx - 1]

                        # 只保留置信度高于阈值的点位
                        if confidence >= self.confidence_threshold:
                            # 转换到原始影像坐标系
                            original_x = center_x + tile.offset_x
                            original_y = center_y + tile.offset_y

                            points.append({
                                "x": original_x,
                                "y": original_y,
                                "confidence": float(confidence),
                                "superpixel_id": int(sp_idx),
                                "tile_index": tile.tile_index,
                            })

            result = {
                "tile_index": tile.tile_index,
                "tile_row": tile.row_index,
                "tile_col": tile.col_index,
                "num_superpixels": len(patches),
                "num_positive": np.sum(np.array(detections) == 1),
                "points": points,
            }

            logger.info(
                f"分块 {tile.tile_index} 检测完成: "
                f"超像素数={result['num_superpixels']}, "
                f"病害木数={result['num_positive']}, "
                f"检测点数={len(points)}"
            )
            return True, result, "分块检测成功"

        except Exception as e:
            logger.error(f"分块 {tile.tile_index} 检测失败: {str(e)}")
            return False, None, f"分块检测失败: {str(e)}"

    def detect_on_tiled_image(
        self,
        image_data: np.ndarray,
        tile_size: int = DEFAULT_TILE_SIZE,
        padding_mode: str = "pad",
        use_parallel: bool = True,
        num_workers: Optional[int] = 8,
    ) -> Tuple[bool, Optional[Dict], str]:
        """
        对分块影像进行病害木检测

        影像会被自动分块为 1024×1024 的分块，每个分块独立进行模型推理，
        然后将结果合并回原始影像坐标系。
        支持并行处理多个分块，默认使用 8 个工作进程。

        Args:
            image_data: 原始影像数据 (H, W, C)
            tile_size: 分块尺寸（默认 1024×1024）
            padding_mode: 边缘处理方式 ("pad" 或 "crop")
            use_parallel: 是否使用并行处理
            num_workers: 工作进程数（默认 8）

        Returns:
            (检测是否成功, 检测结果字典, 错误信息或成功消息)
        """
        try:
            if image_data is None or image_data.size == 0:
                return False, None, "影像数据为空"

            H, W, C = image_data.shape
            logger.info(
                f"开始分块检测: 影像尺寸={W}x{H}, 分块尺寸={tile_size}x{tile_size}"
            )

            # 第一步：生成分块
            success, tiles, msg = TilingService.generate_tiles(
                image_data,
                tile_size=tile_size,
                padding_mode=padding_mode,
            )
            if not success:
                return False, None, msg

            logger.info(f"已生成 {len(tiles)} 个分块")

            # 第二步：处理分块
            if use_parallel:
                # 并行处理
                logger.info("使用并行处理分块")

                # 为每个瓦片准备参数元组
                tile_args = [
                    (self, tile)
                    for tile in tiles
                ]

                success, tile_results, errors, msg = (
                    ParallelProcessingService.process_tiles_parallel(
                        tile_args,
                        _process_tile_for_parallel,
                        num_workers=num_workers,
                        error_handling="log",
                    )
                )

                if not success and len(tile_results) == 0:
                    return False, None, msg

                # 过滤掉错误结果
                valid_results = [r for r in tile_results if r is not None and "error" not in r]
                logger.info(
                    f"并行处理完成: {len(valid_results)} 个成功, {len(errors)} 个失败"
                )
            else:
                # 顺序处理
                logger.info("使用顺序处理分块")
                valid_results = []
                for tile in tiles:
                    success, result, msg = self._process_single_tile(tile)
                    if success:
                        valid_results.append(result)
                    else:
                        logger.error(f"分块 {tile.tile_index} 处理失败: {msg}")

            if not valid_results:
                return False, None, "所有分块处理失败"

            # 第三步：合并结果
            all_points = []
            total_superpixels = 0
            total_positive = 0

            for tile_result in valid_results:
                all_points.extend(tile_result["points"])
                total_superpixels += tile_result["num_superpixels"]
                total_positive += tile_result["num_positive"]

            logger.info(
                f"共检测到 {len(all_points)} 个病害木点位, "
                f"总超像素数={total_superpixels}, "
                f"病害木超像素数={total_positive}"
            )

            # 第四步：合并相邻检测结果
            success, merged_points, msg = self.merge_adjacent_detections(all_points)
            if not success:
                logger.warning(f"点位合并失败: {msg}")
                merged_points = all_points

            # 第五步：结果输出
            result = {
                "points": merged_points,
                "n_tiles": len(tiles),
                "n_successful_tiles": len(valid_results),
                "total_superpixels": total_superpixels,
                "total_positive": total_positive,
                "tile_size": tile_size,
                "image_size": (W, H),
                "method": "分块深度学习检测方法",
                "description": "基于 1024×1024 分块的深度学习病害木检测",
            }

            logger.info("分块检测完成")
            return True, result, "分块检测成功"

        except Exception as e:
            logger.error(f"分块检测失败: {str(e)}")
            return False, None, f"分块检测失败: {str(e)}"

    def merge_adjacent_detections(
        self,
        points: List[Dict],
        merge_distance: float = 50.0,
    ) -> Tuple[bool, Optional[List[Dict]], str]:
        """
        合并相邻或重叠的检测结果

        Args:
            points: 检测点位列表
            merge_distance: 合并距离阈值

        Returns:
            (合并是否成功, 合并后的点位列表, 错误信息或成功消息)
        """
        try:
            if not points:
                return True, [], "点位列表为空"

            merged_points = []
            used = set()

            for i, point1 in enumerate(points):
                if i in used:
                    continue

                # 找到所有相邻的点位
                cluster = [point1]
                used.add(i)

                for j, point2 in enumerate(points):
                    if j <= i or j in used:
                        continue

                    # 计算距离
                    distance = np.sqrt(
                        (point1["x"] - point2["x"]) ** 2
                        + (point1["y"] - point2["y"]) ** 2
                    )

                    if distance <= merge_distance:
                        cluster.append(point2)
                        used.add(j)

                # 计算聚类的平均坐标和置信度
                avg_x = int(np.mean([p["x"] for p in cluster]))
                avg_y = int(np.mean([p["y"] for p in cluster]))
                avg_confidence = np.mean([p["confidence"] for p in cluster])

                merged_points.append({
                    "x": avg_x,
                    "y": avg_y,
                    "confidence": float(avg_confidence),
                    "cluster_size": len(cluster),
                })

            logger.info(
                f"点位合并完成: {len(points)} -> {len(merged_points)}"
            )

            return True, merged_points, "点位合并成功"

        except Exception as e:
            logger.error(f"点位合并失败: {str(e)}")
            return False, None, f"点位合并失败: {str(e)}"
