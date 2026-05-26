"""
病害木检测服务模块
用于对待检测影像进行病害木检测

支持统一的 1024×1024 分块处理和并行处理
"""

import torch
import torch.nn as nn
import numpy as np
import time
from typing import Tuple, Optional, List, Dict
import logging

from backend.utils.slic_processor import SLICProcessor
from backend.utils.tile_utils import TilingService, Tile, DEFAULT_TILE_SIZE
from backend.services.parallel_processing import ParallelProcessingService
from scipy.spatial import KDTree

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

            # 执行 SLIC 超像素分割（含耗时统计与资源预警）
            slic_start = time.time()
            success, labels, message = SLICProcessor.apply_slic_segmentation(
                image_data
            )
            slic_time = time.time() - slic_start
            logger.info(
                f"[SLIC_TIMING] segmentation_time={slic_time:.2f}s, "
                f"image_shape={image_data.shape}"
            )
            if slic_time > 30:
                logger.warning(
                    f"[SLIC_SLOW] SLIC 超像素分割耗时过长 ({slic_time:.1f}s), "
                    f"image_shape={image_data.shape}, 建议减小影像或增加 num_segments"
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
            inference_start = time.time()

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

            inference_time = time.time() - inference_start

            # 构建检测结果
            result = {
                "labels": labels,
                "detections": np.array(detections),
                "confidences": np.array(confidences),
                "num_superpixels": len(patches),
                "num_positive": np.sum(np.array(detections) == 1),
                "inference_time": inference_time,
            }

            logger.info(
                f"检测完成: 总超像素数={result['num_superpixels']}, "
                f"病害木超像素数={result['num_positive']}, "
                f"推理时间={inference_time:.3f}s"
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

            # 执行 SLIC 超像素分割（含耗时统计与资源预警）
            slic_start = time.time()
            success, labels, message = SLICProcessor.apply_slic_segmentation(
                tile_data
            )
            slic_time = time.time() - slic_start
            logger.info(
                f"[SLIC_TIMING] tile={tile.tile_index}, segmentation_time={slic_time:.2f}s, "
                f"tile_shape={tile_data.shape}"
            )
            if slic_time > 10:
                logger.warning(
                    f"[SLIC_SLOW] tile={tile.tile_index} SLIC 分割耗时过长 "
                    f"({slic_time:.1f}s), tile_shape={tile_data.shape}"
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

    def detect_from_file(
        self,
        image_path: str,
        tile_size: int = DEFAULT_TILE_SIZE,
        padding_mode: str = "pad",
        use_parallel: bool = True,
        num_workers: Optional[int] = 8,
    ) -> Tuple[bool, Optional[Dict], str]:
        """
        基于磁盘文件的流式监督病害木检测（适用于大型遥感影像）。

        直接从磁盘文件按需读取分块进行深度学习推理，避免将完整影像加载到内存。
        使用分批处理策略：每批最多加载 (num_workers * 2) 个分块，处理完立即释放。
        与 detect_on_tiled_image 功能等价，但不依赖内存中的 numpy 数组。

        Args:
            image_path: 影像文件路径
            tile_size: 分块尺寸（默认 1024×1024）
            padding_mode: 边缘处理方式 ("pad" 或 "crop")
            use_parallel: 是否使用并行处理
            num_workers: 工作进程数（默认 8）

        Returns:
            (检测是否成功, 检测结果字典, 错误信息或成功消息)
        """
        from backend.utils.image_reader import ImageReader
        import gc

        try:
            # 获取影像信息（不加载完整数据到内存）
            success, info, msg = ImageReader.get_image_info(image_path)
            if not success:
                return False, None, f"获取影像信息失败: {msg}"

            W = info["width"]
            H = info["height"]
            logger.info(
                f"开始基于文件的分块检测: 影像尺寸={W}x{H}, 分块尺寸={tile_size}x{tile_size}"
            )

            # 计算总瓦片数量
            n_rows = (H + tile_size - 1) // tile_size
            n_cols = (W + tile_size - 1) // tile_size
            total_tiles = n_rows * n_cols
            logger.info(f"预计总分块数: {total_tiles} ({n_rows}行 x {n_cols}列)")

            # 第一步：从磁盘分批生成并处理分块
            batch_size = max(num_workers * 2, 4)
            all_valid_results = []
            tile_generator = TilingService.generate_tiles_from_file(
                image_path,
                tile_size=tile_size,
                padding_mode=padding_mode,
            )

            batch_tiles = []
            tile_counter = 0

            for tile in tile_generator:
                batch_tiles.append(tile)
                tile_counter += 1

                if len(batch_tiles) >= batch_size or tile_counter == total_tiles:
                    batch_start = tile_counter - len(batch_tiles) + 1
                    logger.info(
                        f"处理第 {batch_start}-{tile_counter}/{total_tiles} 个分块 "
                        f"(batch_size={len(batch_tiles)})"
                    )

                    # 处理本批分块
                    if use_parallel:
                        tile_args = [(self, t) for t in batch_tiles]
                        success, batch_results, errors, msg = (
                            ParallelProcessingService.process_tiles_parallel(
                                tile_args,
                                _process_tile_for_parallel,
                                num_workers=num_workers,
                                error_handling="log",
                            )
                        )
                        if success or batch_results:
                            valid_batch = [r for r in batch_results if r is not None and "error" not in r]
                            all_valid_results.extend(valid_batch)
                            if errors:
                                logger.warning(f"批次有 {len(errors)} 个分块失败")
                    else:
                        for t in batch_tiles:
                            s, r, m = self._process_single_tile(t)
                            if s:
                                all_valid_results.append(r)
                            else:
                                logger.error(f"分块 {t.tile_index} 处理失败: {m}")

                    # 释放批次分块数据
                    batch_tiles.clear()
                    gc.collect()

            logger.info(f"所有批次处理完成，成功: {len(all_valid_results)}/{total_tiles} 个分块")

            if not all_valid_results:
                return False, None, "所有分块处理失败"

            # 第二步：合并结果
            all_points = []
            total_superpixels = 0
            total_positive = 0

            for tile_result in all_valid_results:
                all_points.extend(tile_result["points"])
                total_superpixels += tile_result["num_superpixels"]
                total_positive += tile_result["num_positive"]

            logger.info(
                f"共检测到 {len(all_points)} 个病害木点位, "
                f"总超像素数={total_superpixels}, "
                f"病害木超像素数={total_positive}"
            )

            # 第三步：合并相邻检测结果
            success, merged_points, msg = self.merge_adjacent_detections(all_points)
            if not success:
                logger.warning(f"点位合并失败: {msg}")
                merged_points = all_points

            # 第四步：结果输出
            result = {
                "points": merged_points,
                "n_tiles": total_tiles,
                "n_successful_tiles": len(all_valid_results),
                "total_superpixels": total_superpixels,
                "total_positive": total_positive,
                "tile_size": tile_size,
                "image_size": (W, H),
                "method": "分块深度学习检测方法（基于文件流式批处理）",
                "description": "基于磁盘流式批处理的 1024×1024 分块深度学习病害木检测",
            }

            # 释放中间变量
            del all_valid_results
            gc.collect()

            logger.info("基于文件的分块检测完成")
            return True, result, "基于文件的分块检测成功"

        except Exception as e:
            logger.error(f"基于文件的分块检测失败: {str(e)}")
            return False, None, f"基于文件的分块检测失败: {str(e)}"

    def merge_adjacent_detections(
        self,
        points: List[Dict],
        merge_distance: float = 50.0,
    ) -> Tuple[bool, Optional[List[Dict]], str]:
        """
        合并相邻或重叠的检测结果（KD-Tree 空间索引优化，O(N log N)）。

        Args:
            points: 检测点位列表
            merge_distance: 合并距离阈值

        Returns:
            (合并是否成功, 合并后的点位列表, 错误信息或成功消息)
        """
        try:
            if not points:
                return True, [], "点位列表为空"

            n = len(points)

            # 少量点位直接使用原始算法（避免 KD-Tree 构建开销）
            if n < 50:
                merged_points = []
                used = set()

                for i, point1 in enumerate(points):
                    if i in used:
                        continue

                    cluster = [point1]
                    used.add(i)

                    for j, point2 in enumerate(points):
                        if j <= i or j in used:
                            continue

                        distance = np.sqrt(
                            (point1["x"] - point2["x"]) ** 2
                            + (point1["y"] - point2["y"]) ** 2
                        )

                        if distance <= merge_distance:
                            cluster.append(point2)
                            used.add(j)

                    avg_x = int(np.mean([p["x"] for p in cluster]))
                    avg_y = int(np.mean([p["y"] for p in cluster]))
                    avg_confidence = np.mean([p["confidence"] for p in cluster])

                    merged_points.append({
                        "x": avg_x,
                        "y": avg_y,
                        "confidence": float(avg_confidence),
                        "cluster_size": len(cluster),
                    })
            else:
                # 使用 KD-Tree 进行空间索引加速（O(N log N)）
                coords = np.array([[p["x"], p["y"]] for p in points], dtype=np.float64)
                tree = KDTree(coords)

                merged_points = []
                used = np.zeros(n, dtype=bool)

                for i in range(n):
                    if used[i]:
                        continue

                    # 查询以当前点为中心、merge_distance 为半径的所有邻居
                    neighbor_indices = tree.query_ball_point(coords[i], merge_distance)
                    cluster_indices = [idx for idx in neighbor_indices if not used[idx]]

                    if not cluster_indices:
                        continue

                    # 标记所有聚类成员为已使用
                    for idx in cluster_indices:
                        used[idx] = True

                    cluster = [points[idx] for idx in cluster_indices]
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
