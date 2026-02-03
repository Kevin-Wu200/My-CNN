"""
无监督病害木检测服务模块
基于光谱、纹理和空间特征的传统非监督分类方法
不使用深度学习模型，不依赖人工标注

支持统一的 1024×1024 分块处理和并行处理
"""

import numpy as np
from pathlib import Path
from typing import Tuple, Optional, Dict, List
import logging
from skimage.color import rgb2gray
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from scipy.ndimage import label, center_of_mass
from scipy import ndimage
import cv2

from backend.utils.tile_utils import TilingService, Tile, DEFAULT_TILE_SIZE
from backend.services.parallel_processing import ParallelProcessingService

logger = logging.getLogger(__name__)


class UnsupervisedDiseaseDetectionService:
    """无监督病害木检测服务类"""

    def __init__(self):
        """初始化服务"""
        self.scaler = StandardScaler()
        self.kmeans = None
        self.feature_matrix = None
        self.spatial_ref = None
        self.tile_size = DEFAULT_TILE_SIZE

    def normalize_image(
        self, image_data: np.ndarray, nodata_value: Optional[float] = None
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        第一步：影像读取与标准化处理

        Args:
            image_data: 影像数据 (H, W, B)
            nodata_value: NoData 像元值

        Returns:
            (处理是否成功, 归一化后的影像数据, 错误信息或成功消息)
        """
        try:
            if image_data is None or image_data.size == 0:
                return False, None, "影像数据为空"

            # 转换为浮点型数组
            normalized_data = image_data.astype(np.float32)

            # 对每个波段进行归一化处理，使像元值落入 [0,1]
            for band_idx in range(normalized_data.shape[2]):
                band_data = normalized_data[:, :, band_idx]

                # 处理 NoData 像元
                if nodata_value is not None:
                    band_data[band_data == nodata_value] = np.nan

                # Min-Max 归一化
                band_min = np.nanmin(band_data)
                band_max = np.nanmax(band_data)

                if band_max - band_min > 0:
                    normalized_data[:, :, band_idx] = (
                        band_data - band_min
                    ) / (band_max - band_min)
                else:
                    normalized_data[:, :, band_idx] = 0

            logger.info("影像归一化处理完成")
            return True, normalized_data, "影像归一化成功"

        except Exception as e:
            logger.error(f"影像归一化失败: {str(e)}")
            return False, None, f"影像归一化失败: {str(e)}"

    def extract_spectral_features(
        self, image_data: np.ndarray
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        第二步 2.1：光谱特征构建

        病害机理：松材线虫病害导致针叶失水、叶绿素下降，
        使红波段反射增强、绿波段反射减弱

        Args:
            image_data: 归一化后的影像数据 (H, W, B)

        Returns:
            (处理是否成功, 光谱特征矩阵, 错误信息或成功消息)
        """
        try:
            H, W, B = image_data.shape

            # 确保至少有 RGB 三个波段
            if B < 3:
                return False, None, "影像波段数不足，需要至少 3 个波段"

            # 提取 RGB 波段（假设前三个波段为 RGB）
            R = image_data[:, :, 0]
            G = image_data[:, :, 1]
            B_band = image_data[:, :, 2]

            # 初始化光谱特征矩阵
            # 特征包括：原始 RGB、R/G、G/B、(R-G)/(R+G+ε)
            spectral_features = np.zeros((H * W, 6), dtype=np.float32)

            # 展平影像
            R_flat = R.reshape(-1)
            G_flat = G.reshape(-1)
            B_flat = B_band.reshape(-1)

            # 原始 RGB 值
            spectral_features[:, 0] = R_flat
            spectral_features[:, 1] = G_flat
            spectral_features[:, 2] = B_flat

            # 波段比值特征
            eps = 1e-8
            spectral_features[:, 3] = R_flat / (G_flat + eps)  # R/G
            spectral_features[:, 4] = G_flat / (B_flat + eps)  # G/B

            # 归一化差异特征
            spectral_features[:, 5] = (R_flat - G_flat) / (
                R_flat + G_flat + eps
            )  # (R-G)/(R+G+ε)

            logger.info(f"光谱特征构建完成，特征维度: {spectral_features.shape}")
            return True, spectral_features, "光谱特征构建成功"

        except Exception as e:
            logger.error(f"光谱特征构建失败: {str(e)}")
            return False, None, f"光谱特征构建失败: {str(e)}"

    def extract_texture_features(
        self, image_data: np.ndarray, window_size: int = 3
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        第二步 2.2：纹理特征构建

        使用局部统计特征计算纹理特征
        病害机理：松材线虫病害木树冠结构破碎、分布不均，
        导致局部纹理更加粗糙

        Args:
            image_data: 归一化后的影像数据 (H, W, B)
            window_size: 滑动窗口大小 (3 或 5)

        Returns:
            (处理是否成功, 纹理特征矩阵, 错误信息或成功消息)
        """
        try:
            H, W, B = image_data.shape

            # 转换为灰度影像
            if B >= 3:
                gray = rgb2gray(image_data[:, :, :3])
            else:
                gray = image_data[:, :, 0]

            # 初始化纹理特征矩阵
            # 特征包括：局部方差、局部对比度、局部能量
            texture_features = np.zeros((H * W, 3), dtype=np.float32)

            # 对每个像元计算其邻域的纹理特征
            pad = window_size // 2
            gray_padded = np.pad(gray, pad, mode="edge")

            for i in range(H):
                for j in range(W):
                    # 提取窗口
                    window = gray_padded[i : i + window_size, j : j + window_size]

                    # 计算局部统计特征
                    # 1. 局部方差（对比度）
                    local_variance = np.var(window)

                    # 2. 局部对比度（最大值 - 最小值）
                    local_contrast = np.max(window) - np.min(window)

                    # 3. 局部能量（平方和）
                    local_energy = np.sum(window ** 2)

                    idx = i * W + j
                    texture_features[idx, 0] = local_variance
                    texture_features[idx, 1] = local_contrast
                    texture_features[idx, 2] = local_energy

            logger.info(f"纹理特征构建完成，特征维度: {texture_features.shape}")
            return True, texture_features, "纹理特征构建成功"

        except Exception as e:
            logger.error(f"纹理特征构建失败: {str(e)}")
            return False, None, f"纹理特征构建失败: {str(e)}"

    def construct_feature_matrix(
        self,
        image_data: np.ndarray,
        window_size: int = 3,
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        第二步 2.3 和第三步：特征融合与标准化

        Args:
            image_data: 归一化后的影像数据 (H, W, B)
            window_size: 纹理特征窗口大小

        Returns:
            (处理是否成功, 标准化后的特征矩阵, 错误信息或成功消息)
        """
        try:
            # 提取光谱特征
            success, spectral_features, msg = self.extract_spectral_features(
                image_data
            )
            if not success:
                return False, None, msg

            # 提取纹理特征
            success, texture_features, msg = self.extract_texture_features(
                image_data, window_size
            )
            if not success:
                return False, None, msg

            # 特征融合
            feature_matrix = np.hstack([spectral_features, texture_features])

            # 特征标准化（零均值、单位方差）
            feature_matrix_normalized = self.scaler.fit_transform(feature_matrix)

            self.feature_matrix = feature_matrix_normalized

            logger.info(
                f"特征矩阵构建完成，形状: {feature_matrix_normalized.shape}"
            )
            return True, feature_matrix_normalized, "特征矩阵构建成功"

        except Exception as e:
            logger.error(f"特征矩阵构建失败: {str(e)}")
            return False, None, f"特征矩阵构建失败: {str(e)}"

    def kmeans_clustering(
        self, feature_matrix: np.ndarray, n_clusters: int = 4
    ) -> Tuple[bool, Optional[np.ndarray], Optional[np.ndarray], str]:
        """
        第四步 4.1：K-means 聚类

        Args:
            feature_matrix: 标准化后的特征矩阵 (N, D)
            n_clusters: 聚类类别数 K

        Returns:
            (处理是否成功, 聚类标签, 聚类中心, 错误信息或成功消息)
        """
        try:
            if feature_matrix is None or feature_matrix.size == 0:
                return False, None, None, "特征矩阵为空"

            # 执行 K-means 聚类
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = kmeans.fit_predict(feature_matrix)
            centers = kmeans.cluster_centers_

            self.kmeans = kmeans

            logger.info(f"K-means 聚类完成，类别数: {n_clusters}")
            return True, labels, centers, "K-means 聚类成功"

        except Exception as e:
            logger.error(f"K-means 聚类失败: {str(e)}")
            return False, None, None, f"K-means 聚类失败: {str(e)}"

    def identify_disease_candidates(
        self,
        image_data: np.ndarray,
        labels: np.ndarray,
        centers: np.ndarray,
        spectral_features: np.ndarray,
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        第五步：病害木候选类别判定

        寻找满足以下特征的类别：
        - 红波段值偏高
        - 绿波段值偏低
        - 纹理对比度较高

        Args:
            image_data: 原始影像数据
            labels: 聚类标签
            centers: 聚类中心
            spectral_features: 光谱特征矩阵

        Returns:
            (处理是否成功, 病害木候选像元标记, 错误信息或成功消息)
        """
        try:
            H, W, B = image_data.shape
            candidate_mask = np.zeros((H * W,), dtype=np.uint8)

            # 对每个聚类中心分析特征
            for cluster_id in range(centers.shape[0]):
                # 获取该类别的光谱特征（前 6 维）
                center_spectral = centers[cluster_id, :6]

                # 提取 R、G 值（假设在光谱特征的前两维）
                R_mean = center_spectral[0]
                G_mean = center_spectral[1]

                # 获取该类别的纹理特征（后 3 维）
                center_texture = centers[cluster_id, 6:]
                contrast_mean = center_texture[0]

                # 判定条件：红波段偏高、绿波段偏低、纹理对比度较高
                # 使用相对阈值
                R_threshold = np.mean(centers[:, 0])
                G_threshold = np.mean(centers[:, 1])
                contrast_threshold = np.mean(centers[:, 6])

                is_disease_candidate = (
                    R_mean > R_threshold * 1.1
                    and G_mean < G_threshold * 0.9
                    and contrast_mean > contrast_threshold * 1.1
                )

                if is_disease_candidate:
                    # 标记该类别的所有像元为病害木候选像元
                    candidate_mask[labels == cluster_id] = 1

                    logger.info(
                        f"类别 {cluster_id} 被识别为病害木候选类别 "
                        f"(R={R_mean:.3f}, G={G_mean:.3f}, Contrast={contrast_mean:.3f})"
                    )

            logger.info(f"病害木候选像元识别完成，候选像元数: {np.sum(candidate_mask)}")
            return True, candidate_mask, "病害木候选类别判定成功"

        except Exception as e:
            logger.error(f"病害木候选类别判定失败: {str(e)}")
            return False, None, f"病害木候选类别判定失败: {str(e)}"

    def spatial_postprocessing(
        self,
        candidate_mask: np.ndarray,
        image_shape: Tuple[int, int],
        min_area: int = 50,
    ) -> Tuple[bool, Optional[np.ndarray], Optional[List[Dict]], str]:
        """
        第六步：空间后处理

        - 连通域分析
        - 去除面积小于阈值的小斑块
        - 合并相邻候选区域
        - 计算几何中心

        Args:
            candidate_mask: 病害木候选像元标记 (N,)
            image_shape: 影像形状 (H, W)
            min_area: 最小斑块面积阈值

        Returns:
            (处理是否成功, 处理后的掩膜, 病害木中心点位列表, 错误信息或成功消息)
        """
        try:
            H, W = image_shape

            # 将一维掩膜转换为二维
            mask_2d = candidate_mask.reshape((H, W))

            # 连通域分析
            labeled_array, num_features = label(mask_2d)

            logger.info(f"连通域分析完成，连通域数: {num_features}")

            # 去除面积小于阈值的小斑块
            processed_mask = np.zeros_like(mask_2d)
            center_points = []

            for region_id in range(1, num_features + 1):
                region_mask = labeled_array == region_id
                region_area = np.sum(region_mask)

                if region_area >= min_area:
                    processed_mask[region_mask] = 1

                    # 计算几何中心
                    coords = np.where(region_mask)
                    center_y = np.mean(coords[0])
                    center_x = np.mean(coords[1])

                    center_points.append(
                        {
                            "x": float(center_x),
                            "y": float(center_y),
                            "area": int(region_area),
                        }
                    )

            logger.info(
                f"空间后处理完成，保留斑块数: {len(center_points)}, "
                f"最小面积阈值: {min_area}"
            )
            return True, processed_mask, center_points, "空间后处理成功"

        except Exception as e:
            logger.error(f"空间后处理失败: {str(e)}")
            return False, None, None, f"空间后处理失败: {str(e)}"

    def _process_single_tile(
        self,
        tile: Tile,
        n_clusters: int = 4,
        min_area: int = 50,
        nodata_value: Optional[float] = None,
    ) -> Tuple[bool, Optional[Dict], str]:
        """
        处理单个分块

        Args:
            tile: Tile 对象
            n_clusters: K-means 聚类类别数
            min_area: 最小斑块面积阈值
            nodata_value: NoData 像元值

        Returns:
            (处理是否成功, 处理结果字典, 错误信息或成功消息)
        """
        try:
            tile_data = tile.data
            H, W = tile_data.shape[:2]

            # 第一步：影像归一化
            success, normalized_image, msg = self.normalize_image(
                tile_data, nodata_value
            )
            if not success:
                return False, None, msg

            # 第二步和第三步：特征构建与标准化
            success, feature_matrix, msg = self.construct_feature_matrix(
                normalized_image
            )
            if not success:
                return False, None, msg

            # 第四步：K-means 聚类
            success, labels, centers, msg = self.kmeans_clustering(
                feature_matrix, n_clusters
            )
            if not success:
                return False, None, msg

            # 提取光谱特征用于候选类别判定
            success, spectral_features, msg = self.extract_spectral_features(
                normalized_image
            )
            if not success:
                return False, None, msg

            # 第五步：病害木候选类别判定
            success, candidate_mask, msg = self.identify_disease_candidates(
                normalized_image, labels, centers, spectral_features
            )
            if not success:
                return False, None, msg

            # 第六步：空间后处理
            success, processed_mask, center_points, msg = self.spatial_postprocessing(
                candidate_mask, (H, W), min_area
            )
            if not success:
                return False, None, msg

            # 转换中心点坐标到原始影像坐标系
            original_center_points = []
            for point in center_points:
                original_point = {
                    "x": point["x"] + tile.offset_x,
                    "y": point["y"] + tile.offset_y,
                    "area": point["area"],
                    "tile_index": tile.tile_index,
                }
                original_center_points.append(original_point)

            result = {
                "tile_index": tile.tile_index,
                "tile_row": tile.row_index,
                "tile_col": tile.col_index,
                "candidate_mask": processed_mask,
                "center_points": original_center_points,
                "n_clusters": n_clusters,
                "n_candidates": len(original_center_points),
            }

            logger.info(
                f"分块 {tile.tile_index} 检测完成: {len(original_center_points)} 个候选点"
            )
            return True, result, "分块检测成功"

        except Exception as e:
            logger.error(f"分块 {tile.tile_index} 检测失败: {str(e)}")
            return False, None, f"分块检测失败: {str(e)}"

    def detect_on_tiled_image(
        self,
        image_data: np.ndarray,
        n_clusters: int = 4,
        min_area: int = 50,
        nodata_value: Optional[float] = None,
        tile_size: int = DEFAULT_TILE_SIZE,
        padding_mode: str = "pad",
        use_parallel: bool = True,
        num_workers: Optional[int] = None,
    ) -> Tuple[bool, Optional[Dict], str]:
        """
        对分块影像进行无监督病害木检测

        影像会被自动分块为 1024×1024 的分块，每个分块独立处理，
        然后将结果合并回原始影像坐标系。
        支持并行处理多个分块。

        Args:
            image_data: 原始影像数据 (H, W, B)
            n_clusters: K-means 聚类类别数
            min_area: 最小斑块面积阈值
            nodata_value: NoData 像元值
            tile_size: 分块尺寸（默认 1024×1024）
            padding_mode: 边缘处理方式 ("pad" 或 "crop")
            use_parallel: 是否使用并行处理
            num_workers: 工作进程数（如果为 None，则自动检测）

        Returns:
            (检测是否成功, 检测结果字典, 错误信息或成功消息)
        """
        try:
            if image_data is None or image_data.size == 0:
                return False, None, "影像数据为空"

            H, W, B = image_data.shape
            logger.info(
                f"开始分块检测: 影像尺寸={W}x{H}, 分块尺寸={tile_size}x{tile_size}"
            )

            # 第一步：生成分块
            success, tiles, msg = TilingService.generate_tiles(
                image_data,
                tile_size=tile_size,
                padding_mode=padding_mode,
                spatial_ref=self.spatial_ref,
            )
            if not success:
                return False, None, msg

            logger.info(f"已生成 {len(tiles)} 个分块")

            # 第二步：处理分块
            if use_parallel:
                # 并行处理
                logger.info("使用并行处理分块")

                def process_tile_wrapper(tile):
                    success, result, msg = self._process_single_tile(
                        tile, n_clusters, min_area, nodata_value
                    )
                    if not success:
                        return {"error": msg, "tile_index": tile.tile_index}
                    return result

                success, tile_results, errors, msg = (
                    ParallelProcessingService.process_tiles_parallel(
                        tiles,
                        process_tile_wrapper,
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
                    success, result, msg = self._process_single_tile(
                        tile, n_clusters, min_area, nodata_value
                    )
                    if success:
                        valid_results.append(result)
                    else:
                        logger.error(f"分块 {tile.tile_index} 处理失败: {msg}")

            if not valid_results:
                return False, None, "所有分块处理失败"

            # 第三步：合并结果
            all_center_points = []
            for tile_result in valid_results:
                all_center_points.extend(tile_result["center_points"])

            logger.info(f"共检测到 {len(all_center_points)} 个候选点")

            # 第四步：结果输出
            result = {
                "center_points": all_center_points,
                "n_tiles": len(tiles),
                "n_successful_tiles": len(valid_results),
                "n_clusters": n_clusters,
                "n_candidates": len(all_center_points),
                "tile_size": tile_size,
                "image_size": (W, H),
                "method": "分块无监督分类方法",
                "description": "基于 1024×1024 分块的光谱、纹理和空间特征无监督病害木检测",
            }

            logger.info("分块检测完成")
            return True, result, "分块检测成功"

        except Exception as e:
            logger.error(f"分块检测失败: {str(e)}")
            return False, None, f"分块检测失败: {str(e)}"

    def detect(
        self,
        image_data: np.ndarray,
        n_clusters: int = 4,
        min_area: int = 50,
        nodata_value: Optional[float] = None,
    ) -> Tuple[bool, Optional[Dict], str]:
        """
        执行完整的无监督病害木检测流程

        Args:
            image_data: 原始影像数据 (H, W, B)
            n_clusters: K-means 聚类类别数
            min_area: 最小斑块面积阈值
            nodata_value: NoData 像元值

        Returns:
            (检测是否成功, 检测结果字典, 错误信息或成功消息)
        """
        try:
            H, W, B = image_data.shape

            # 第一步：影像归一化
            success, normalized_image, msg = self.normalize_image(
                image_data, nodata_value
            )
            if not success:
                return False, None, msg

            # 第二步和第三步：特征构建与标准化
            success, feature_matrix, msg = self.construct_feature_matrix(
                normalized_image
            )
            if not success:
                return False, None, msg

            # 第四步：K-means 聚类
            success, labels, centers, msg = self.kmeans_clustering(
                feature_matrix, n_clusters
            )
            if not success:
                return False, None, msg

            # 提取光谱特征用于候选类别判定
            success, spectral_features, msg = self.extract_spectral_features(
                normalized_image
            )
            if not success:
                return False, None, msg

            # 第五步：病害木候选类别判定
            success, candidate_mask, msg = self.identify_disease_candidates(
                normalized_image, labels, centers, spectral_features
            )
            if not success:
                return False, None, msg

            # 第六步：空间后处理
            success, processed_mask, center_points, msg = self.spatial_postprocessing(
                candidate_mask, (H, W), min_area
            )
            if not success:
                return False, None, msg

            # 第七步：结果输出
            result = {
                "candidate_mask": processed_mask,
                "center_points": center_points,
                "n_clusters": n_clusters,
                "n_candidates": len(center_points),
                "method": "传统非监督分类方法",
                "description": "基于光谱、纹理和空间特征的无监督病害木检测",
            }

            logger.info("无监督病害木检测完成")
            return True, result, "无监督病害木检测成功"

        except Exception as e:
            logger.error(f"无监督病害木检测失败: {str(e)}")
            return False, None, f"无监督病害木检测失败: {str(e)}"
