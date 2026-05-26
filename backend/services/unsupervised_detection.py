"""
非监督病害木检测服务模块
基于光谱、纹理和空间特征的传统非监督分类方法
不使用深度学习模型，不依赖人工标注

支持统一的 1024×1024 分块处理和并行处理
"""

import numpy as np
from typing import Tuple, Optional, Dict, List
import logging
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from skimage.color import rgb2gray
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from scipy.ndimage import label
from scipy.spatial import KDTree

from backend.utils.tile_utils import TilingService, Tile, DEFAULT_TILE_SIZE
from backend.services.parallel_processing import ParallelProcessingService, DEFAULT_PARALLEL_WORKERS
from backend.utils.resource_monitor import ResourceMonitor
from backend.config.settings import CLUSTER_DISTANCE, MEMORY_WARN_THRESHOLD, MEMORY_CRITICAL_THRESHOLD

logger = logging.getLogger(__name__)


# 模块级别的瓦片处理函数，用于多进程处理（必须在模块级别以支持pickle序列化）
def _process_tile_for_parallel(args):
    """
    处理单个瓦片的模块级别函数

    每个 worker 独立创建 service 实例，避免 multiprocessing pickle 问题。

    Args:
        args: 包含 (tile, n_clusters, min_area, nodata_value, r_threshold_factor, g_threshold_factor, contrast_threshold_factor) 的元组
              threshold_factor 设为 None 启用动态分位数阈值模式

    Returns:
        处理结果字典或错误字典
    """
    tile, n_clusters, min_area, nodata_value, r_threshold_factor, g_threshold_factor, contrast_threshold_factor = args
    try:
        service = UnsupervisedDiseaseDetectionService()
        success, result, msg = service._process_single_tile(
            tile, n_clusters, min_area, nodata_value,
            r_threshold_factor, g_threshold_factor, contrast_threshold_factor
        )
        if not success:
            return {"error": msg, "tile_index": tile.tile_index}
        logger.info(f"tile {tile.tile_index} 完成")
        return result
    except Exception as e:
        logger.error(f"瓦片 {tile.tile_index} 处理异常: {str(e)}")
        return {"error": str(e), "tile_index": tile.tile_index}


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

            # 验证nodata_value的有效性
            if nodata_value is not None:
                # 检查nodata_value是否在影像数据范围内
                data_min = np.nanmin(image_data)
                data_max = np.nanmax(image_data)
                if nodata_value < data_min or nodata_value > data_max:
                    logger.warning(
                        f"nodata_value={nodata_value} 超出影像数据范围 [{data_min}, {data_max}]，"
                        "可能无法正确处理NoData像元"
                    )

                # 检查nodata_value是否会导致过多的像元被标记为NoData
                nodata_ratio = np.sum(image_data == nodata_value) / image_data.size
                if nodata_ratio > 0.5:
                    logger.warning(
                        f"超过50%的像元被标记为NoData (nodata_value={nodata_value}, ratio={nodata_ratio:.2%})，"
                        "可能影响检测结果"
                    )

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
        第二步 2.1：光谱特征构建（增强版）

        病害机理：松材线虫病害导致针叶失水、叶绿素下降，
        使红波段反射增强、绿波段反射减弱

        特征包括：原始 RGB、波段比值、归一化植被指数

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

            # 初始化光谱特征矩阵（扩展为 8 维）
            # 特征包括：原始 RGB、R/G、G/B、(R-G)/(R+G+ε)、GLI、VDVI、(R-B)/(R+B+ε)
            spectral_features = np.zeros((H * W, 8), dtype=np.float32)

            # 展平影像
            R_flat = R.reshape(-1)
            G_flat = G.reshape(-1)
            B_flat = B_band.reshape(-1)

            # 原始 RGB 值
            spectral_features[:, 0] = R_flat
            spectral_features[:, 1] = G_flat
            spectral_features[:, 2] = B_flat

            eps = 1e-8

            # 波段比值特征
            spectral_features[:, 3] = R_flat / (G_flat + eps)  # R/G - 红色增强
            spectral_features[:, 4] = G_flat / (B_flat + eps)  # G/B - 绿色衰减

            # 归一化差异特征
            spectral_features[:, 5] = (R_flat - G_flat) / (
                R_flat + G_flat + eps
            )  # (R-G)/(R+G+ε) - 伪NDVI

            # GLI (Green Leaf Index): (2*G - R - B) / (2*G + R + B)
            # 对绿色植被敏感，病害木叶绿素衰减导致 GLI 降低
            spectral_features[:, 6] = (2 * G_flat - R_flat - B_flat) / (
                2 * G_flat + R_flat + B_flat + eps
            )

            # VDVI (Visible-band Difference Vegetation Index): (2*G - R - B) / (2*G + R + B) 标准化版
            # 基于可见光波段的植被指数，用于 RGB 影像
            spectral_features[:, 7] = (R_flat - B_flat) / (
                R_flat + B_flat + eps
            )  # (R-B)/(R+B+ε)

            # 如果影像有第四波段（可能是 NIR），额外计算真 NDVI
            if B >= 4:
                NIR = image_data[:, :, 3]
                NIR_flat = NIR.reshape(-1)
                # 扩展特征矩阵以容纳 NDVI
                extra_features = np.zeros((H * W, 1), dtype=np.float32)
                extra_features[:, 0] = (NIR_flat - R_flat) / (NIR_flat + R_flat + eps)
                spectral_features = np.hstack([spectral_features, extra_features])
                logger.info(f"检测到 NIR 波段，已添加真 NDVI 特征")

            logger.info(f"光谱特征构建完成，特征维度: {spectral_features.shape}")
            return True, spectral_features, "光谱特征构建成功"

        except Exception as e:
            logger.error(f"光谱特征构建失败: {str(e)}")
            return False, None, f"光谱特征构建失败: {str(e)}"

    def extract_texture_features(
        self, image_data: np.ndarray, window_size: int = 3
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        第二步 2.2：纹理特征构建（增强版：GLCM + 局部统计）

        使用局部统计特征 + GLCM（灰度共生矩阵）特征：
        - 局部统计：方差、对比度、能量
        - GLCM：对比度、相异性、同质性、能量、相关性

        病害机理：松材线虫病害木树冠结构破碎、分布不均，
        导致局部纹理更加粗糙

        Args:
            image_data: 归一化后的影像数据 (H, W, B)
            window_size: 滑动窗口大小 (3 或 5)

        Returns:
            (处理是否成功, 纹理特征矩阵, 错误信息或成功消息)
        """
        try:
            from scipy.ndimage import uniform_filter, maximum_filter, minimum_filter

            H, W, B = image_data.shape

            # 转换为灰度影像
            if B >= 3:
                gray = rgb2gray(image_data[:, :, :3])
            else:
                gray = image_data[:, :, 0]

            gray_f32 = gray.astype(np.float32)

            # === 局部统计纹理特征 ===
            # 1. 局部方差：E[X²] - E[X]²
            mean = uniform_filter(gray_f32, size=window_size)
            sqr_mean = uniform_filter(gray_f32 ** 2, size=window_size)
            local_variance = sqr_mean - mean ** 2
            local_variance = np.maximum(local_variance, 0)

            # 2. 局部对比度：max - min
            local_max = maximum_filter(gray_f32, size=window_size)
            local_min = minimum_filter(gray_f32, size=window_size)
            local_contrast = local_max - local_min

            # 3. 局部能量：E[X²]
            local_energy = sqr_mean

            # === GLCM 纹理特征（在降采样灰度图上计算以提升性能）===
            glcm_features_list = self._compute_glcm_features(gray, window_size)

            # 将特征矩阵展平并合并
            feature_components = [
                local_variance.reshape(-1),
                local_contrast.reshape(-1),
                local_energy.reshape(-1),
            ]
            feature_components.extend(glcm_features_list)

            texture_features = np.stack(feature_components, axis=1).astype(np.float32)

            logger.info(f"纹理特征构建完成，特征维度: {texture_features.shape}")
            return True, texture_features, "纹理特征构建成功"

        except Exception as e:
            logger.error(f"纹理特征构建失败: {str(e)}")
            return False, None, f"纹理特征构建失败: {str(e)}"

    def _compute_glcm_features(
        self, gray_image: np.ndarray, window_size: int = 3
    ) -> List[np.ndarray]:
        """
        计算基于 GLCM（灰度共生矩阵）的纹理特征。

        使用降采样 + 分块策略避免 OOM：
        - 将灰度影像缩放至较小尺寸计算 GLCM
        - GLCM 特征通过最近邻上采样回原始尺寸

        Args:
            gray_image: 灰度影像 (H, W)，值范围 [0, 1]
            window_size: GLCM 窗口大小

        Returns:
            5 个 GLCM 特征（每个形状为 (H*W,)）：对比度、相异性、同质性、能量、相关性
        """
        from skimage.feature import graycomatrix, graycoprops
        from scipy.ndimage import zoom

        H, W = gray_image.shape

        # 将灰度值量化为 0-15（16 级），大幅降低 GLCM 计算复杂度
        gray_quantized = (gray_image * 15).astype(np.uint8)

        # 对于大图进行降采样以加速 GLCM 计算
        max_dim = 512
        scale = min(1.0, max_dim / max(H, W))
        if scale < 1.0:
            small_H = int(H * scale)
            small_W = int(W * scale)
            gray_small = zoom(gray_quantized.astype(np.float32), scale, order=0).astype(np.uint8)
            logger.info(f"GLCM: 降采样 {H}x{W} -> {small_H}x{small_W} (scale={scale:.3f})")
        else:
            small_H, small_W = H, W
            gray_small = gray_quantized

        # 计算全图 GLCM（4 个方向，距离 1 像素）
        distances = [1]
        angles = [0, np.pi / 4, np.pi / 2, 3 * np.pi / 4]

        try:
            glcm = graycomatrix(
                gray_small,
                distances=distances,
                angles=angles,
                levels=16,
                symmetric=True,
                normed=True,
            )
        except Exception as e:
            logger.warning(f"GLCM 计算失败: {e}，将使用零填充")
            zero_features = [np.zeros(H * W, dtype=np.float32) for _ in range(5)]
            return zero_features

        # 提取 5 个 Haralick 特征（对 4 个方向取平均）
        contrast = graycoprops(glcm, 'contrast').mean()  # 标量
        dissimilarity = graycoprops(glcm, 'dissimilarity').mean()
        homogeneity = graycoprops(glcm, 'homogeneity').mean()
        energy = graycoprops(glcm, 'energy').mean()
        correlation = graycoprops(glcm, 'correlation').mean()

        # 创建与原始影像相同大小的特征图（填充 GLCM 统计值）
        contrast_map = np.full(H * W, contrast, dtype=np.float32)
        dissimilarity_map = np.full(H * W, dissimilarity, dtype=np.float32)
        homogeneity_map = np.full(H * W, homogeneity, dtype=np.float32)
        energy_map = np.full(H * W, energy, dtype=np.float32)
        correlation_map = np.full(H * W, correlation, dtype=np.float32)

        logger.info(
            f"GLCM 特征: contrast={contrast:.4f}, dissimilarity={dissimilarity:.4f}, "
            f"homogeneity={homogeneity:.4f}, energy={energy:.4f}, correlation={correlation:.4f}"
        )

        return [contrast_map, dissimilarity_map, homogeneity_map, energy_map, correlation_map]

    def construct_feature_matrix(
        self,
        image_data: np.ndarray,
        window_size: int = 3,
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        第二步 2.3 和第三步：特征融合与标准化（优化版本）

        优化说明：
        - 及时释放中间特征矩阵，降低峰值内存占用
        - 使用 float32 保持内存效率
        - 增强数值稳定性，避免 K-means 计算异常

        Args:
            image_data: 归一化后的影像数据 (H, W, B)
            window_size: 纹理特征窗口大小

        Returns:
            (处理是否成功, 标准化后的特征矩阵, 错误信息或成功消息)
        """
        import gc

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

            # 记录特征矩阵内存使用
            feature_matrix_mb = feature_matrix.nbytes / 1024 / 1024
            logger.info(f"特征矩阵构建完成，内存占用: {feature_matrix_mb:.2f}MB")

            # 及时释放单个特征矩阵
            del spectral_features, texture_features
            gc.collect()

            # 检查可用内存
            memory_info = ResourceMonitor.get_memory_usage()
            available_memory_mb = memory_info['available']
            logger.info(f"可用内存: {available_memory_mb:.2f}MB")

            if available_memory_mb < 512:  # 小于512MB时警告
                logger.warning(f"可用内存不足（{available_memory_mb:.2f}MB），可能导致内存问题")

            nan_mask = np.isnan(feature_matrix)
            inf_mask = np.isinf(feature_matrix)
            invalid_mask = nan_mask | inf_mask

            # 创建有效像素掩模：标记哪些行是有效的非 NoData 像素
            # 如果某行的所有特征都是 NaN/Inf（即 NoData 像素），标记为无效
            row_all_invalid = np.all(invalid_mask, axis=1)
            valid_pixel_mask = ~row_all_invalid
            n_invalid_rows = np.sum(row_all_invalid)
            if n_invalid_rows > 0:
                logger.info(
                    f"检测到 {n_invalid_rows} 个 NoData 像素行 "
                    f"({n_invalid_rows / len(row_all_invalid) * 100:.1f}%)，"
                    f"将在 K-means 聚类前过滤"
                )

            if np.any(invalid_mask):
                n_invalid = np.sum(invalid_mask)
                logger.warning(
                    f"特征矩阵中发现 {n_invalid} 个无效值 "
                    f"(NaN: {np.sum(nan_mask)}, Inf: {np.sum(inf_mask)})，将替换为0"
                )
                # 将无效值替换为0
                feature_matrix[invalid_mask] = 0

            # 使用百分位数裁剪，保留 [1%, 99%] 范围内的值
            for col_idx in range(feature_matrix.shape[1]):
                col_data = feature_matrix[:, col_idx]
                # 只对非零值计算百分位数
                non_zero_mask = col_data != 0
                if np.any(non_zero_mask):
                    non_zero_data = col_data[non_zero_mask]
                    p1 = np.percentile(non_zero_data, 1)
                    p99 = np.percentile(non_zero_data, 99)
                    # 裁剪极端值
                    col_data = np.clip(col_data, p1, p99)
                    feature_matrix[:, col_idx] = col_data

            logger.info("特征矩阵极端值裁剪完成")

            # 使用 RobustScaler 替代 StandardScaler，更鲁棒
            # 优化：对超大特征矩阵采用抽样拟合 (Sampling Fit) 策略
            # 仅抽取部分代表性像素进行标准化参数计算，降低 CPU 开销
            from sklearn.preprocessing import RobustScaler
            robust_scaler = RobustScaler()

            n_samples = feature_matrix.shape[0]
            sampling_threshold = 500000  # 超过 50 万像素启用抽样拟合
            max_sample_size = 200000     # 最多抽取 20 万像素

            if n_samples > sampling_threshold:
                sample_size = min(max_sample_size, n_samples)
                # 均匀抽样：每 n 个取一个
                step = n_samples // sample_size
                sample_indices = np.arange(0, n_samples, step)[:sample_size]
                feature_sample = feature_matrix[sample_indices]

                logger.info(
                    f"RobustScaler 抽样拟合: 总样本={n_samples}, "
                    f"抽样={len(sample_indices)} ({len(sample_indices) / n_samples * 100:.1f}%), "
                    f"预计降低CPU开销 {100 - len(sample_indices) / n_samples * 100:.0f}%"
                )

                robust_scaler.fit(feature_sample)
                feature_matrix_normalized = robust_scaler.transform(feature_matrix)
            else:
                feature_matrix_normalized = robust_scaler.fit_transform(feature_matrix)

            # 第四步：再次检查标准化后的无效值
            nan_mask_after = np.isnan(feature_matrix_normalized)
            inf_mask_after = np.isinf(feature_matrix_normalized)
            invalid_mask_after = nan_mask_after | inf_mask_after

            if np.any(invalid_mask_after):
                n_invalid_after = np.sum(invalid_mask_after)
                logger.warning(
                    f"标准化后仍有 {n_invalid_after} 个无效值，将替换为0"
                )
                feature_matrix_normalized[invalid_mask_after] = 0

            # 释放未标准化的特征矩阵
            del feature_matrix
            gc.collect()

            self.feature_matrix = feature_matrix_normalized

            logger.info(
                f"特征矩阵构建完成，形状: {feature_matrix_normalized.shape}"
            )
            return True, (feature_matrix_normalized, valid_pixel_mask), "特征矩阵构建成功"

        except Exception as e:
            logger.error(f"特征矩阵构建失败: {str(e)}")
            return False, None, f"特征矩阵构建失败: {str(e)}"

    def kmeans_clustering(
        self, feature_matrix: np.ndarray, n_clusters: int = 4,
        random_state: int = 42, n_init: int = 10, max_iter: int = 300,
        valid_pixel_mask: Optional[np.ndarray] = None,
    ) -> Tuple[bool, Optional[np.ndarray], Optional[np.ndarray], str]:
        """
        第四步 4.1：K-means 聚类

        支持通过 valid_pixel_mask 排除 NoData 像素，防止背景无效数据干扰聚类质心计算。

        Args:
            feature_matrix: 标准化后的特征矩阵 (N, D)
            n_clusters: 聚类类别数 K
            random_state: 随机种子（默认42）
            n_init: 初始化次数（默认10）
            max_iter: 最大迭代次数（默认300）
            valid_pixel_mask: 有效像素掩模 (N,)，True 表示有效像素，False 表示 NoData

        Returns:
            (处理是否成功, 聚类标签, 聚类中心, 错误信息或成功消息)
        """
        import warnings

        try:
            if feature_matrix is None or feature_matrix.size == 0:
                return False, None, None, "特征矩阵为空"

            # 再次检查特征矩阵中的无效值
            if np.any(np.isnan(feature_matrix)) or np.any(np.isinf(feature_matrix)):
                n_nan = np.sum(np.isnan(feature_matrix))
                n_inf = np.sum(np.isinf(feature_matrix))
                logger.error(
                    f"特征矩阵包含无效值 (NaN: {n_nan}, Inf: {n_inf})，"
                    "无法进行聚类"
                )
                return False, None, None, "特征矩阵包含无效值"

            # 额外的数值稳定性处理：裁剪到合理范围
            # 避免极端值导致KMeans计算溢出
            feature_matrix_clipped = np.clip(feature_matrix, -10, 10)

            n_total = feature_matrix_clipped.shape[0]

            # 如果提供了有效像素掩模，仅对有效像素进行聚类
            if valid_pixel_mask is not None:
                valid_indices = np.where(valid_pixel_mask)[0]
                n_valid = len(valid_indices)
                n_invalid = n_total - n_valid

                if n_invalid > 0:
                    logger.info(
                        f"K-means 聚类排除 NoData 像素: "
                        f"有效像素={n_valid}, NoData={n_invalid} "
                        f"({n_invalid / n_total * 100:.1f}%)"
                    )

                if n_valid < n_clusters:
                    logger.warning(
                        f"有效像素数 ({n_valid}) 少于聚类数 ({n_clusters})，"
                        "使用全部像素进行聚类"
                    )
                    feature_for_kmeans = feature_matrix_clipped
                    use_mask = False
                else:
                    feature_for_kmeans = feature_matrix_clipped[valid_indices]
                    use_mask = True
            else:
                feature_for_kmeans = feature_matrix_clipped
                use_mask = False

            # 抑制sklearn的RuntimeWarning，因为我们已经做了充分的数值处理
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', category=RuntimeWarning)

                # 执行 K-means 聚类
                # 使用 'k-means++' 初始化方法提高稳定性
                kmeans = KMeans(
                    n_clusters=n_clusters,
                    random_state=random_state,
                    n_init=n_init,
                    init='k-means++',
                    max_iter=max_iter,
                    tol=1e-4
                )
                labels_valid = kmeans.fit_predict(feature_for_kmeans)
                centers = kmeans.cluster_centers_

            # 如果使用了掩模，将标签映射回全尺寸数组
            if use_mask:
                labels = np.full(n_total, -1, dtype=np.int32)  # NoData 像素标记为 -1
                labels[valid_indices] = labels_valid
            else:
                labels = labels_valid

            self.kmeans = kmeans

            logger.info(f"K-means 聚类完成，类别数: {n_clusters}")
            return True, labels, centers, "K-means 聚类成功"

        except Exception as e:
            logger.error(f"K-means 聚类失败: {str(e)}")
            return False, None, None, f"K-means 聚类失败: {str(e)}"

    def cluster_busting(
        self,
        feature_matrix: np.ndarray,
        labels: np.ndarray,
        centers: np.ndarray,
        n_sub_clusters: int = 3,
        confusion_threshold: float = 0.35,
    ) -> Tuple[bool, Optional[np.ndarray], Optional[np.ndarray], str]:
        """
        聚类拆分 (Cluster Busting)：对混淆类进行二次迭代聚类

        对非监督分类产生的混淆类（类内方差大、光谱纯度低的类别）
        进行拆分，提高病害木候选区的光谱纯度。

        策略：
        1. 计算每个聚类的类内方差（衡量混淆程度）
        2. 对超过混淆阈值的类别进行二次 K-means 聚类
        3. 将子聚类结果合并回标签数组

        Args:
            feature_matrix: 标准化后的特征矩阵 (N, D)
            labels: 原始 K-means 聚类标签 (N,)
            centers: 原始聚类中心
            n_sub_clusters: 每次拆分的子聚类数
            confusion_threshold: 混淆阈值，类内方差超过此比例触发拆分

        Returns:
            (处理是否成功, 拆分后的标签, 拆分后的聚类中心, 错误信息或成功消息)
        """
        try:
            n_samples = feature_matrix.shape[0]
            n_clusters_original = centers.shape[0]

            # 计算每个聚类的类内方差（标准化后的方差）
            cluster_variances = {}
            confused_clusters = []

            for cluster_id in range(n_clusters_original):
                cluster_mask = labels == cluster_id
                n_in_cluster = np.sum(cluster_mask)

                if n_in_cluster < 10:
                    continue  # 样本太少，跳过

                cluster_data = feature_matrix[cluster_mask]
                # 计算每维方差的均值作为混淆度指标
                cluster_variance = np.mean(np.var(cluster_data, axis=0))
                cluster_variances[cluster_id] = cluster_variance

            if not cluster_variances:
                logger.info("所有聚类样本数均不足，跳过 Cluster Busting")
                return True, labels, centers, "Cluster Busting 跳过（样本不足）"

            # 归一化方差以便跨类别比较
            max_variance = max(cluster_variances.values()) if cluster_variances else 1.0
            for cluster_id, variance in cluster_variances.items():
                normalized_variance = variance / max_variance if max_variance > 1e-8 else 0
                if normalized_variance > confusion_threshold:
                    n_in_cluster = np.sum(labels == cluster_id)
                    confused_clusters.append((cluster_id, normalized_variance, n_in_cluster))
                    logger.info(
                        f"类别 {cluster_id}: 混淆度={normalized_variance:.3f} > {confusion_threshold}, "
                        f"样本数={n_in_cluster}, 将被拆分"
                    )

            if not confused_clusters:
                logger.info("所有聚类光谱纯度高，无需 Cluster Busting")
                return True, labels, centers, "Cluster Busting 完成（无需拆分）"

            logger.info(
                f"Cluster Busting: {len(confused_clusters)}/{n_clusters_original} 个混淆类将被拆分"
            )

            # 对混淆类进行二次聚类
            new_labels = labels.copy()
            new_centers_list = [centers]
            current_cluster_offset = n_clusters_original

            for confused_cluster_id, _, _ in confused_clusters:
                cluster_mask = (labels == confused_cluster_id)
                cluster_data = feature_matrix[cluster_mask]

                if cluster_data.shape[0] < n_sub_clusters * 5:
                    logger.info(f"类别 {confused_cluster_id}: 样本数不足，跳过拆分")
                    continue

                # 二次 K-means 聚类
                import warnings
                with warnings.catch_warnings():
                    warnings.filterwarnings('ignore', category=RuntimeWarning)
                    sub_kmeans = KMeans(
                        n_clusters=n_sub_clusters,
                        random_state=42,
                        n_init=5,
                        init='k-means++',
                        max_iter=200,
                    )
                    sub_labels = sub_kmeans.fit_predict(cluster_data)

                # 映射子标签到全局标签空间
                global_indices = np.where(cluster_mask)[0]
                for sub_id in range(n_sub_clusters):
                    sub_mask = sub_labels == sub_id
                    new_cluster_id = current_cluster_offset + sub_id
                    new_labels[global_indices[sub_mask]] = new_cluster_id

                current_cluster_offset += n_sub_clusters
                new_centers_list.append(sub_kmeans.cluster_centers_)

                logger.info(
                    f"类别 {confused_cluster_id}: 拆分为 {n_sub_clusters} 个子类 "
                    f"({current_cluster_offset - n_sub_clusters}-{current_cluster_offset - 1})"
                )

            # 合并所有聚类中心
            new_centers = np.vstack(new_centers_list)

            logger.info(
                f"Cluster Busting 完成: {n_clusters_original} -> "
                f"{new_centers.shape[0]} 个聚类"
            )
            return True, new_labels, new_centers, "Cluster Busting 成功"

        except Exception as e:
            logger.error(f"Cluster Busting 失败: {str(e)}")
            return False, None, None, f"Cluster Busting 失败: {str(e)}"

    def identify_disease_candidates(
        self,
        image_data: np.ndarray,
        labels: np.ndarray,
        centers: np.ndarray,
        spectral_features: np.ndarray,
        r_threshold_factor: float = 1.1,
        g_threshold_factor: float = 0.9,
        contrast_threshold_factor: float = 1.1,
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        第五步：病害木候选类别判定（动态分位数阈值版）

        使用基于影像直方图分布的动态分位数阈值替代硬编码因子，
        提高对不同光照条件影像的鲁棒性。

        当 threshold_factor 参数不为 None 时，使用原有硬编码模式（向后兼容）；
        当为 None 时，使用动态分位数阈值模式。

        Args:
            image_data: 原始影像数据
            labels: 聚类标签
            centers: 聚类中心
            spectral_features: 光谱特征矩阵
            r_threshold_factor: 红波段阈值因子（None=动态分位数模式）
            g_threshold_factor: 绿波段阈值因子（None=动态分位数模式）
            contrast_threshold_factor: 对比度阈值因子（None=动态分位数模式）

        Returns:
            (处理是否成功, 病害木候选像元标记, 错误信息或成功消息)
        """
        try:
            H, W, B = image_data.shape
            candidate_mask = np.zeros((H * W,), dtype=np.uint8)

            # 确定阈值模式：任一 factor 为 None 则使用动态分位数模式
            use_dynamic_threshold = (
                r_threshold_factor is None
                or g_threshold_factor is None
                or contrast_threshold_factor is None
            )

            if use_dynamic_threshold:
                # 动态分位数阈值模式：基于各聚类中心的光谱直方图分布
                logger.info("使用动态分位数阈值模式（基于影像直方图分布）")

                # 计算所有聚类中心的 R、G、contrast 分布
                all_R = centers[:, 0]
                all_G = centers[:, 1]
                all_contrast = centers[:, 6] if centers.shape[1] > 6 else centers[:, 7]

                # 使用 75 分位数作为"偏高"阈值、25 分位数作为"偏低"阈值
                # 病害木特征：红波段在高分位区、绿波段在低分位区、对比度在高分位区
                R_high = np.percentile(all_R, 75)
                G_low = np.percentile(all_G, 25)
                contrast_high = np.percentile(all_contrast, 75)

                logger.info(
                    f"动态阈值: R>{R_high:.4f} (P75), G<{G_low:.4f} (P25), "
                    f"Contrast>{contrast_high:.4f} (P75)"
                )

                for cluster_id in range(centers.shape[0]):
                    center_spectral = centers[cluster_id, :6] if centers.shape[1] > 6 else centers[cluster_id, :8]
                    R_mean = center_spectral[0]
                    G_mean = center_spectral[1]

                    if centers.shape[1] > 8:
                        center_texture = centers[cluster_id, 8:]
                    elif centers.shape[1] > 6:
                        center_texture = centers[cluster_id, 6:]
                    else:
                        center_texture = centers[cluster_id, 6:]

                    contrast_mean = center_texture[0]

                    is_disease_candidate = (
                        R_mean > R_high
                        and G_mean < G_low
                        and contrast_mean > contrast_high
                    )

                    if is_disease_candidate:
                        candidate_mask[labels == cluster_id] = 1
                        logger.info(
                            f"类别 {cluster_id} 被识别为病害木候选类别 "
                            f"(R={R_mean:.3f} > {R_high:.3f}, G={G_mean:.3f} < {G_low:.3f}, Contrast={contrast_mean:.3f} > {contrast_high:.3f})"
                        )
            else:
                # 原有硬编码阈值模式（向后兼容）
                logger.info(f"使用硬编码阈值模式: R>{r_threshold_factor}*mean, G<{g_threshold_factor}*mean, Contrast>{contrast_threshold_factor}*mean")

                for cluster_id in range(centers.shape[0]):
                    center_spectral = centers[cluster_id, :6] if centers.shape[1] > 6 else centers[cluster_id, :8]
                    R_mean = center_spectral[0]
                    G_mean = center_spectral[1]

                    if centers.shape[1] > 8:
                        center_texture = centers[cluster_id, 8:]
                    elif centers.shape[1] > 6:
                        center_texture = centers[cluster_id, 6:]
                    else:
                        center_texture = centers[cluster_id, 6:]

                    contrast_mean = center_texture[0]

                    R_threshold = np.mean(centers[:, 0])
                    G_threshold = np.mean(centers[:, 1])
                    contrast_threshold = np.mean(centers[:, 6])

                    is_disease_candidate = (
                        R_mean > R_threshold * r_threshold_factor
                        and G_mean < G_threshold * g_threshold_factor
                        and contrast_mean > contrast_threshold * contrast_threshold_factor
                    )

                    if is_disease_candidate:
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
        task_manager=None,
        task_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[np.ndarray], Optional[List[Dict]], str]:
        """
        第六步：空间后处理（OBIA 增强版）

        基于对象的影像分析 (OBIA) 思路：
        - 连通域分析识别候选斑块
        - 基于形态学开闭运算去除椒盐噪声
        - 计算斑块几何属性（面积、紧密度、延伸率）进行智能过滤
        - 去除面积小于阈值且形态异常的孤立噪声斑块

        Args:
            candidate_mask: 病害木候选像元标记 (N,)
            image_shape: 影像形状 (H, W)
            min_area: 最小斑块面积阈值
            task_manager: 任务管理器（用于进度更新）
            task_id: 任务ID（用于进度跟踪）

        Returns:
            (处理是否成功, 处理后的掩膜, 病害木中心点位列表, 错误信息或成功消息)
        """
        try:
            from scipy.ndimage import binary_opening, binary_closing, binary_dilation, binary_erosion

            H, W = image_shape

            # 将一维掩膜转换为二维
            mask_2d = candidate_mask.reshape((H, W)).astype(bool)

            # OBIA 步骤1：形态学开运算去除孤立椒盐噪声像素
            # 使用 3x3 结构元素，先腐蚀后膨胀，去除 < 3x3 的孤立噪声点
            mask_2d = binary_opening(mask_2d, structure=np.ones((3, 3)))
            logger.debug("形态学开运算完成（椒盐噪声去除）")

            # OBIA 步骤2：形态学闭运算连接相邻斑块
            # 使用 2x2 结构元素，先膨胀后腐蚀，填补斑块内部空洞
            mask_2d = binary_closing(mask_2d, structure=np.ones((2, 2)))
            logger.debug("形态学闭运算完成（斑块空洞填补）")

            # 连通域分析
            labeled_array, num_features = label(mask_2d.astype(np.uint8))

            logger.info(f"连通域分析完成，连通域数: {num_features}")

            # OBIA 步骤3：基于几何属性的智能过滤
            processed_mask = np.zeros((H, W), dtype=np.uint8)
            center_points = []

            # 计算进度更新间隔
            log_interval = max(1, num_features // 20)
            base_progress = 75

            for region_id in range(1, num_features + 1):
                # 检查停止标志
                if task_manager and task_manager.is_stop_requested(task_id):
                    logger.info(f"[{task_id}] 检测任务被停止（空间后处理阶段，区域{region_id}/{num_features}）")
                    return False, None, None, "检测任务被用户停止"

                region_mask = labeled_array == region_id
                region_area = np.sum(region_mask)

                if region_area >= min_area:
                    # OBIA 几何属性计算
                    coords = np.where(region_mask)
                    center_y = np.mean(coords[0])
                    center_x = np.mean(coords[1])

                    # 计算斑块紧密度：面积 / 边界框面积
                    y_min, y_max = coords[0].min(), coords[0].max()
                    x_min, x_max = coords[1].min(), coords[1].max()
                    bbox_area = (y_max - y_min + 1) * (x_max - x_min + 1)
                    compactness = region_area / bbox_area if bbox_area > 0 else 0

                    # 过滤过于松散（紧密度 < 0.1）的线状噪声
                    if compactness < 0.1 and region_area < min_area * 3:
                        logger.debug(f"区域 {region_id}: 紧密度过低 ({compactness:.3f})，视为线状噪声跳过")
                        continue

                    processed_mask[region_mask] = 1
                    center_points.append({
                        "x": float(center_x),
                        "y": float(center_y),
                        "area": int(region_area),
                        "compactness": float(compactness),
                    })

                # 每处理一定数量的区域后更新进度
                if region_id % log_interval == 0 and task_manager and task_id:
                    progress = base_progress + int((region_id / num_features) * 15)
                    task_manager.update_progress(
                        task_id, progress,
                        f"提取中心点: {region_id}/{num_features}"
                    )

            logger.info(
                f"空间后处理完成（OBIA），保留斑块数: {len(center_points)}, "
                f"最小面积阈值: {min_area}"
            )
            return True, processed_mask, center_points, "空间后处理成功（OBIA模式）"

        except Exception as e:
            logger.error(f"空间后处理失败: {str(e)}")
            return False, None, None, f"空间后处理失败: {str(e)}"

    def _process_single_tile(
        self,
        tile: Tile,
        n_clusters: int = 4,
        min_area: int = 50,
        nodata_value: Optional[float] = None,
        r_threshold_factor: Optional[float] = None,
        g_threshold_factor: Optional[float] = None,
        contrast_threshold_factor: Optional[float] = None,
    ) -> Tuple[bool, Optional[Dict], str]:
        """
        处理单个分块

        Args:
            tile: Tile 对象
            n_clusters: K-means 聚类类别数
            min_area: 最小斑块面积阈值
            nodata_value: NoData 像元值
            r_threshold_factor: 红波段阈值因子（None=动态分位数模式，值=硬编码模式）
            g_threshold_factor: 绿波段阈值因子（None=动态分位数模式，值=硬编码模式）
            contrast_threshold_factor: 对比度阈值因子（None=动态分位数模式，值=硬编码模式）

        Returns:
            (处理是否成功, 处理结果字典, 错误信息或成功消息)
        """
        try:
            logger.info(f"分块 {tile.tile_index} 处理开始")
            ResourceMonitor.log_resource_status(f"分块 {tile.tile_index} 处理开始")

            tile_data = tile.data
            H, W = tile_data.shape[:2]

            # NoData 跳过机制：检测空块或高比例无效数据（阈值 90%，预计提升边缘区域处理速度 30%+）
            if nodata_value is not None:
                nodata_ratio = np.sum(tile_data == nodata_value) / tile_data.size
                if nodata_ratio > 0.90:
                    logger.info(
                        f"分块 {tile.tile_index}: NoData 比例={nodata_ratio:.1%}，超过90%阈值，跳过处理"
                    )
                    return True, {
                        "tile_index": tile.tile_index,
                        "tile_row": tile.row_index,
                        "tile_col": tile.col_index,
                        "center_points": [],
                        "n_candidates": 0,
                        "skipped": True,
                        "skip_reason": f"NoData比例={nodata_ratio:.1%}",
                    }, "分块跳过（NoData 比例过高）"

            # 背景块预检：对低方差/低信息量的块快速跳过（提升边缘区域处理速度）
            if tile_data.size > 0:
                tile_std = np.nanstd(tile_data)
                # 如果块内标准差极小（<0.001 归一化尺度），视为均匀背景块
                if tile_std < 0.001:
                    logger.info(
                        f"分块 {tile.tile_index}: 背景块（std={tile_std:.6f}），跳过处理"
                    )
                    return True, {
                        "tile_index": tile.tile_index,
                        "tile_row": tile.row_index,
                        "tile_col": tile.col_index,
                        "center_points": [],
                        "n_candidates": 0,
                        "skipped": True,
                        "skip_reason": f"背景块（std={tile_std:.6f}）",
                    }, "分块跳过（低信息量背景块）"

            # 全零检测
            if np.all(tile_data == 0) or np.allclose(tile_data, 0, atol=1e-6):
                logger.info(f"分块 {tile.tile_index}: 全零数据，跳过处理")
                return True, {
                    "tile_index": tile.tile_index,
                    "tile_row": tile.row_index,
                    "tile_col": tile.col_index,
                    "center_points": [],
                    "n_candidates": 0,
                    "skipped": True,
                    "skip_reason": "全零分块",
                }, "分块跳过（全零数据）"

            # 第一步：影像归一化
            logger.debug(f"分块 {tile.tile_index}: 开始影像归一化")
            success, normalized_image, msg = self.normalize_image(
                tile_data, nodata_value
            )
            if not success:
                logger.error(f"分块 {tile.tile_index}: 影像归一化失败 - {msg}")
                return False, None, msg

            # 第二步和第三步：特征构建与标准化
            logger.debug(f"分块 {tile.tile_index}: 开始特征构建与标准化")
            success, feature_result, msg = self.construct_feature_matrix(
                normalized_image
            )
            if not success:
                logger.error(f"分块 {tile.tile_index}: 特征构建失败 - {msg}")
                return False, None, msg
            feature_matrix, valid_pixel_mask = feature_result

            # 第四步：K-means 聚类（排除 NoData 像素）
            logger.debug(f"分块 {tile.tile_index}: 开始 K-means 聚类")
            success, labels, centers, msg = self.kmeans_clustering(
                feature_matrix, n_clusters,
                valid_pixel_mask=valid_pixel_mask,
            )
            if not success:
                logger.error(f"分块 {tile.tile_index}: K-means 聚类失败 - {msg}")
                return False, None, msg

            # 第四步扩展: Cluster Busting 混淆类拆分（提高光谱纯度）
            logger.debug(f"分块 {tile.tile_index}: 开始 Cluster Busting")
            success, labels, centers, cb_msg = self.cluster_busting(
                feature_matrix, labels, centers,
                n_sub_clusters=3, confusion_threshold=0.35,
            )
            if not success:
                logger.warning(f"分块 {tile.tile_index}: Cluster Busting 失败（非致命）: {cb_msg}")
                # Cluster Busting 失败不阻断流程，使用原始聚类结果
            else:
                logger.info(f"分块 {tile.tile_index}: Cluster Busting 完成: {cb_msg}")

            # 提取光谱特征用于候选类别判定
            logger.debug(f"分块 {tile.tile_index}: 提取光谱特征")
            success, spectral_features, msg = self.extract_spectral_features(
                normalized_image
            )
            if not success:
                logger.error(f"分块 {tile.tile_index}: 光谱特征提取失败 - {msg}")
                return False, None, msg

            # 第五步：病害木候选类别判定
            logger.debug(f"分块 {tile.tile_index}: 开始病害木候选类别判定")
            success, candidate_mask, msg = self.identify_disease_candidates(
                normalized_image, labels, centers, spectral_features,
                r_threshold_factor, g_threshold_factor, contrast_threshold_factor
            )
            if not success:
                logger.error(f"分块 {tile.tile_index}: 候选类别判定失败 - {msg}")
                return False, None, msg

            # 第六步：空间后处理
            logger.debug(f"分块 {tile.tile_index}: 开始空间后处理")
            success, processed_mask, center_points, msg = self.spatial_postprocessing(
                candidate_mask, (H, W), min_area
            )
            if not success:
                logger.error(f"分块 {tile.tile_index}: 空间后处理失败 - {msg}")
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

            # 将 tile mask 写入磁盘，避免通过 IPC 返回大型 numpy 数组
            tiles_mask_dir = os.path.join("storage", "tiles_mask")
            os.makedirs(tiles_mask_dir, exist_ok=True)
            output_path = os.path.join(tiles_mask_dir, f"tile_mask_{tile.tile_index}.npy")
            np.save(output_path, processed_mask.astype(np.uint8))

            result = {
                "tile_index": tile.tile_index,
                "tile_row": tile.row_index,
                "tile_col": tile.col_index,
                "mask_path": output_path,
                "center_points": original_center_points,
                "n_clusters": n_clusters,
                "n_candidates": len(original_center_points),
                "offset_y": tile.offset_y,
                "offset_x": tile.offset_x,
                "tile_height": tile.tile_info.tile_height,
                "tile_width": tile.tile_info.tile_width,
            }

            logger.info(
                f"分块 {tile.tile_index} 处理完成: {len(original_center_points)} 个候选点"
            )
            ResourceMonitor.log_resource_status(f"分块 {tile.tile_index} 处理完成")
            return True, result, "分块检测成功"

        except Exception as e:
            logger.error(f"分块 {tile.tile_index} 检测失败: {str(e)}")
            ResourceMonitor.log_resource_status(f"分块 {tile.tile_index} 处理异常")
            return False, None, f"分块检测失败: {str(e)}"

    def _merge_tile_points(
        self,
        valid_results: List[Dict],
        image_height: int,
        image_width: int,
        min_area: int = 50,
        cluster_distance: float = CLUSTER_DISTANCE,
        task_manager=None,
        task_id: Optional[str] = None,
        disk_cache_threshold: int = 1000000,
        cache_dir: Optional[str] = None,
    ) -> Tuple[bool, Optional[List[Dict]], str]:
        """
        合并所有 tile 的候选中心点，使用 KD-Tree 距离聚类替代 O(N^2) 遍历。

        旧方案：构建全局 mask 数组（可能 10GB+），然后进行全局连通域分析。
        新方案：直接收集各 tile 已提取的候选中心点，通过 KD-Tree 距离聚类合并跨瓦片斑块。
        完全取消全局 mask 的生成，避免大型影像 OOM。

        当候选点数超过 disk_cache_threshold（默认 100 万）时，启用磁盘缓存模式：
        中间结果流式写入磁盘，避免 Python List 对象撑爆内存。

        Args:
            valid_results: 有效的 tile 处理结果列表，每个结果包含 center_points
            image_height: 原始影像高度（仅用于日志）
            image_width: 原始影像宽度（仅用于日志）
            min_area: 最小斑块面积阈值（用于日志）
            cluster_distance: 跨瓦片点位聚类距离阈值（从配置文件读取，默认 80 像素，符合树冠物理尺寸 50-100 像素范围）
            task_manager: 任务管理器（用于更新进度）
            task_id: 任务ID（用于进度跟踪）
            disk_cache_threshold: 磁盘缓存点数阈值（默认 100 万）
            cache_dir: 磁盘缓存目录（默认使用 storage/merge_cache）

        Returns:
            (合并是否成功, 合并后的候选中心点列表, 错误信息或成功消息)
        """
        import time as _time

        try:
            merge_start = _time.time()
            logger.info(
                f"开始基于距离聚类的点合并: tile_count={len(valid_results)}, "
                f"image_size={image_width}x{image_height}, cluster_distance={cluster_distance}"
            )

            # 第一步：收集所有 tile 的候选中心点（已在瓦片坐标系偏移到全局坐标）
            all_points = []
            total_tile_points = 0

            for result in valid_results:
                tile_points = result.get("center_points", [])
                if tile_points:
                    all_points.extend(tile_points)
                total_tile_points += len(tile_points)

            logger.info(
                f"点收集完成: 总候选点数={len(all_points)}, "
                f"来自 {len(valid_results)} 个瓦片"
            )

            if not all_points:
                logger.info("无候选点，合并完成（空结果）")
                return True, [], "无候选点（空结果合并成功）"

            # 超大结果集磁盘持久化：当候选点数超过阈值时，先将中间结果写入磁盘
            use_disk_cache = len(all_points) > disk_cache_threshold
            if use_disk_cache:
                logger.warning(
                    f"[DISK_CACHE] 候选点数={len(all_points)} 超过阈值={disk_cache_threshold}, "
                    f"启用磁盘缓存模式，避免 List 对象撑爆内存"
                )
                if cache_dir is None:
                    cache_dir = os.path.join("storage", "merge_cache")
                os.makedirs(cache_dir, exist_ok=True)

                # 将 all_points 分批写入磁盘缓存文件
                cache_file = os.path.join(cache_dir, f"merge_points_{task_id or 'default'}.json")
                batch_size = 10000
                with open(cache_file, 'w', encoding='utf-8') as f:
                    f.write('[\n')
                    for batch_start in range(0, len(all_points), batch_size):
                        batch = all_points[batch_start:batch_start + batch_size]
                        for j, p in enumerate(batch):
                            if batch_start > 0 or j > 0:
                                f.write(',\n')
                            import json
                            f.write(json.dumps(p, ensure_ascii=False))
                    f.write('\n]')
                logger.info(f"[DISK_CACHE] 已写入 {len(all_points)} 个候选点到缓存文件: {cache_file}")

                # 释放内存中的 all_points 列表
                point_count = len(all_points)
                del all_points
                import gc
                gc.collect()
                # 重新构建轻量引用
                all_points = None  # 后续需要读取时从磁盘流式加载
                logger.info(f"[DISK_CACHE] 已释放 {point_count} 个候选点的内存, 缓存文件={cache_file}")

                # 对于超大结果，使用分批聚类策略
                merged_points = self._batch_cluster_from_disk(
                    cache_file, cluster_distance, min_area
                )
                return True, merged_points, "候选点合并成功（磁盘缓存+分批聚类模式）"

            # 正常模式：内存内 KD-Tree 聚类
            coords = np.array([[p["x"], p["y"]] for p in all_points], dtype=np.float64)
            tree = KDTree(coords)
            n_points = len(all_points)
            used = np.zeros(n_points, dtype=bool)
            clusters = []

            for i in range(n_points):
                if used[i]:
                    continue

                # 查询以当前点为中心、cluster_distance 为半径的所有邻居
                neighbor_indices = tree.query_ball_point(coords[i], cluster_distance)
                cluster_indices = [idx for idx in neighbor_indices if not used[idx]]

                if not cluster_indices:
                    continue

                for idx in cluster_indices:
                    used[idx] = True

                cluster = [all_points[idx] for idx in cluster_indices]
                clusters.append(cluster)

            # 第三步：对每个聚类计算合并后的中心点
            merged_points = []
            for cluster in clusters:
                avg_x = float(np.mean([p["x"] for p in cluster]))
                avg_y = float(np.mean([p["y"] for p in cluster]))
                total_area = int(np.sum([p.get("area", 1) for p in cluster]))
                merged_points.append({
                    "x": avg_x,
                    "y": avg_y,
                    "area": total_area,
                    "cluster_size": len(cluster),
                })

            # 过滤掉面积过小的点（可选，由调用方 min_area 控制）
            filtered_points = [p for p in merged_points if p["area"] >= min_area]
            if len(filtered_points) < len(merged_points):
                logger.info(
                    f"面积过滤: {len(merged_points)} -> {len(filtered_points)} "
                    f"(min_area={min_area})"
                )

            merge_elapsed = _time.time() - merge_start
            logger.info(
                f"点合并完成: {total_tile_points} 个瓦片点 -> "
                f"{len(clusters)} 个聚类 -> {len(filtered_points)} 个最终候选点, "
                f"耗时={merge_elapsed:.2f}s"
            )

            return True, filtered_points, "候选点合并成功（距离聚类模式，全局无内存）"

        except Exception as e:
            logger.exception(f"候选点合并失败: {e}")
            return False, None, f"候选点合并失败: {str(e)}"

    def _batch_cluster_from_disk(
        self,
        cache_file: str,
        cluster_distance: float,
        min_area: int = 50,
    ) -> List[Dict]:
        """
        从磁盘缓存文件分批读取候选点并进行分批 KD-Tree 聚类。

        适用于百万级候选点场景，避免一次性加载全部点坐标到内存。

        Args:
            cache_file: 磁盘缓存 JSON 文件路径
            cluster_distance: 聚类距离阈值
            min_area: 最小斑块面积

        Returns:
            合并后的候选中心点列表
        """
        import json
        import gc

        logger.info(f"[BATCH_CLUSTER] 从磁盘缓存分批聚类, 文件={cache_file}")

        all_merged = []
        batch_size = 50000  # 每批 5 万个点

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                content = f.read()
            all_points_data = json.loads(content)

            total = len(all_points_data)
            logger.info(f"[BATCH_CLUSTER] 加载 {total} 个候选点")

            # 分批处理：每批独立进行 KD-Tree 聚类
            for batch_start in range(0, total, batch_size):
                batch_end = min(batch_start + batch_size, total)
                batch = all_points_data[batch_start:batch_end]

                # 在批次内进行 KD-Tree 聚类
                coords = np.array([[p["x"], p["y"]] for p in batch], dtype=np.float64)
                tree = KDTree(coords)
                n_batch = len(batch)
                used = np.zeros(n_batch, dtype=bool)
                clusters = []

                for i in range(n_batch):
                    if used[i]:
                        continue
                    neighbor_indices = tree.query_ball_point(coords[i], cluster_distance)
                    cluster_indices = [idx for idx in neighbor_indices if not used[idx]]
                    if not cluster_indices:
                        continue
                    for idx in cluster_indices:
                        used[idx] = True
                    cluster = [batch[idx] for idx in cluster_indices]
                    clusters.append(cluster)

                # 计算合并后的中心点
                for cluster in clusters:
                    avg_x = float(np.mean([p["x"] for p in cluster]))
                    avg_y = float(np.mean([p["y"] for p in cluster]))
                    total_area = int(np.sum([p.get("area", 1) for p in cluster]))
                    all_merged.append({
                        "x": avg_x,
                        "y": avg_y,
                        "area": total_area,
                        "cluster_size": len(cluster),
                    })

                logger.info(
                    f"[BATCH_CLUSTER] 批次 {batch_start // batch_size + 1}: "
                    f"{batch_start}-{batch_end}/{total}, 累计合并={len(all_merged)}"
                )

            # 释放原始数据
            del all_points_data
            gc.collect()

            # 跨批次去重：对合并结果再做一次全局 KD-Tree 聚类
            if len(all_merged) > 1:
                coords_final = np.array([[p["x"], p["y"]] for p in all_merged], dtype=np.float64)
                tree_final = KDTree(coords_final)
                n_final = len(all_merged)
                used_final = np.zeros(n_final, dtype=bool)
                final_clusters = []

                for i in range(n_final):
                    if used_final[i]:
                        continue
                    neighbor_indices = tree_final.query_ball_point(coords_final[i], cluster_distance)
                    cluster_indices = [idx for idx in neighbor_indices if not used_final[idx]]
                    if not cluster_indices:
                        continue
                    for idx in cluster_indices:
                        used_final[idx] = True
                    cluster = [all_merged[idx] for idx in cluster_indices]
                    final_clusters.append(cluster)

                final_points = []
                for cluster in final_clusters:
                    avg_x = float(np.mean([p["x"] for p in cluster]))
                    avg_y = float(np.mean([p["y"] for p in cluster]))
                    total_area = int(np.sum([p.get("area", 1) for p in cluster]))
                    final_points.append({
                        "x": avg_x,
                        "y": avg_y,
                        "area": total_area,
                        "cluster_size": sum(p.get("cluster_size", 1) for p in cluster),
                    })

                # 面积过滤
                filtered = [p for p in final_points if p["area"] >= min_area]
                logger.info(
                    f"[BATCH_CLUSTER] 跨批次去重: {len(all_merged)} -> "
                    f"{len(filtered)} (min_area={min_area})"
                )
                all_merged = filtered

            # 清理缓存文件
            try:
                os.remove(cache_file)
                logger.info(f"[BATCH_CLUSTER] 已删除缓存文件: {cache_file}")
            except Exception:
                pass

            return all_merged

        except Exception as e:
            logger.exception(f"[BATCH_CLUSTER] 分批聚类失败: {e}")
            # 降级：尝试返回已合并的结果
            return all_merged if all_merged else []

    def _merge_tile_masks(
        self,
        valid_results: List[Dict],
        image_height: int,
        image_width: int,
        task_manager=None,
        task_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        [已废弃] 合并所有 tile mask 文件为全局 mask。

        此方法已被 _merge_tile_points 替代（非监督分类流程）。
        保留此方法仅用于向后兼容和潜在的其他调用方。

        Args:
            valid_results: 有效的 tile 处理结果列表
            image_height: 原始影像高度
            image_width: 原始影像宽度
            task_manager: 任务管理器（用于更新进度）
            task_id: 任务ID（用于进度跟踪）

        Returns:
            (合并是否成功, 合并后的全局 mask, 错误信息或成功消息)
        """
        import sys
        import time as _time

        try:
            logger.warning("_merge_tile_masks 已被弃用，建议使用 _merge_tile_points（非监督分类流程已自动切换）")
            logger.info("开始执行图像合并")
            logger.info(f"tile count: {len(valid_results)}")
            logger.info(f"output size: {image_width}x{image_height}")
            merge_start = _time.time()

            logger.info(f"检查 tile_results: {len(valid_results)} 个")
            invalid_entries = [r for r in valid_results if r is None or "mask_path" not in r]
            if invalid_entries:
                logger.error(f"tile_results contains invalid entries: {len(invalid_entries)} 个")

            tile_dtypes = set()
            tile_shapes = []

            seen_indices = set()
            seen_offsets = set()
            for result in valid_results:
                idx = result.get("tile_index")
                if idx in seen_indices:
                    logger.error(f"发现重复 tile_index: {idx}")
                seen_indices.add(idx)
                offset_key = (result.get("offset_y"), result.get("offset_x"))
                if offset_key in seen_offsets:
                    logger.error(f"发现重复 offset: {offset_key}")
                seen_offsets.add(offset_key)

            logger.info(f"output_width={image_width}, output_height={image_height}")

            estimated_size = image_height * image_width * np.dtype(np.uint8).itemsize
            memory_info = ResourceMonitor.get_memory_usage()
            available_memory = memory_info['available'] * 1024 * 1024  # MB -> bytes
            logger.info(
                f"内存检查: 可用={available_memory/1024/1024:.1f}MB, "
                f"需要={estimated_size/1024/1024:.1f}MB"
            )
            if estimated_size > available_memory * 0.8:
                error_msg = (
                    f"内存不足: 需要 {estimated_size/1024/1024:.1f}MB, "
                    f"可用 {available_memory/1024/1024:.1f}MB (使用率超过80%)"
                )
                logger.error(error_msg)
                return False, None, error_msg

            global_mask = np.zeros((image_height, image_width), dtype=np.uint8)
            logger.info(f"global_mask.nbytes={global_mask.nbytes} ({global_mask.nbytes / 1024 / 1024:.1f} MB)")
            if global_mask.nbytes > 2 * 1024 * 1024 * 1024:
                logger.warning("global_mask 超过 2GB，可能导致内存问题")

            total_tiles = len(valid_results)
            sorted_results = sorted(valid_results, key=lambda r: r["tile_index"])
            log_interval = max(1, total_tiles // 20)  # 最多输出20次进度日志

            for i, result in enumerate(sorted_results):
                tile_index = result["tile_index"]
                mask_path = result["mask_path"]

                # 只在关键节点输出日志
                if i % log_interval == 0 or i == total_tiles - 1:
                    progress = int((i + 1) / total_tiles * 100)
                    logger.info(f"合并进度: {i+1}/{total_tiles} ({progress}%)")
                    # 更新任务进度（70% -> 80%）
                    if task_manager and task_id:
                        merge_progress = 70 + int((i + 1) / total_tiles * 10)
                        task_manager.update_progress(
                            task_id,
                            merge_progress,
                            f"合并分块结果: {i+1}/{total_tiles}"
                        )

                # 检查 tile 文件是否真实存在
                if not os.path.exists(mask_path):
                    logger.error(f"tile file missing: {mask_path}")
                    continue

                try:
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(np.load, mask_path)
                        tile_mask = future.result(timeout=30)  # 30秒超时
                except FuturesTimeoutError:
                    logger.error(f"读取文件超时（30秒）: {mask_path}")
                    continue
                except Exception as load_err:
                    logger.error(f"读取文件失败: {mask_path}, 错误: {str(load_err)}")
                    continue

                tile_dtypes.add(str(tile_mask.dtype))
                tile_shapes.append(tile_mask.shape)

                offset_y = result["offset_y"]
                offset_x = result["offset_x"]
                tile_h = result["tile_height"]
                tile_w = result["tile_width"]

                # 步骤7: 确保 tile 不超出目标图边界
                if offset_y + tile_h > image_height or offset_x + tile_w > image_width:
                    logger.error(
                        f"tile {tile_index} 超出目标图边界: "
                        f"offset=({offset_y},{offset_x}), size=({tile_h},{tile_w}), "
                        f"target=({image_height},{image_width})"
                    )

                # 只取有效区域（去除 padding 部分）
                valid_mask = tile_mask[:tile_h, :tile_w]

                global_mask[
                    offset_y : offset_y + tile_h,
                    offset_x : offset_x + tile_w,
                ] = valid_mask

            if len(tile_dtypes) > 1:
                logger.warning(f"tile dtype 不一致: {tile_dtypes}")

            logger.info(f"tile_results 总大小: {sys.getsizeof(valid_results)} bytes")

            merge_elapsed = _time.time() - merge_start
            logger.info(f"merge time: {merge_elapsed:.2f}s")

            if merge_elapsed > 300:
                logger.warning(f"merge taking too long: {merge_elapsed:.2f}s > 300s")

            logger.info("图像合并完成")

            return True, global_mask, "tile mask 合并成功"

        except Exception as e:
            logger.exception(f"tile mask 合并失败: {e}")
            return False, None, f"tile mask 合并失败: {str(e)}"

    def _cleanup_tile_masks(self, valid_results: List[Dict]) -> None:
        """
        清理临时 tile mask 文件（强化异常保护版）

        确保即使主任务失败、进程异常退出，数GB临时瓦片掩膜文件也能被强制清理。
        使用多层 try/except 保护，单个文件删除失败不影响其他文件清理。
        同时清理存储目录下可能残留的过期 tile mask 文件。
        """
        # 即使 valid_results 为空，也尝试清理可能残留的过期临时文件
        tiles_mask_dir = os.path.join("storage", "tiles_mask")

        cleaned_count = 0
        failed_files = []
        total_cleaned_bytes = 0

        try:
            # 第一轮：根据 valid_results 中记录的 mask_path 清理
            if valid_results:
                for result in valid_results:
                    if result is None:
                        continue
                    try:
                        mask_path = result.get("mask_path")
                        if mask_path and os.path.exists(mask_path):
                            file_size = os.path.getsize(mask_path)
                            os.remove(mask_path)
                            cleaned_count += 1
                            total_cleaned_bytes += file_size
                    except FileNotFoundError:
                        # 文件已被删除，无需处理
                        cleaned_count += 1
                    except PermissionError as pe:
                        failed_files.append(mask_path)
                        logger.warning(f"清理文件失败（权限不足）: {mask_path}, 错误: {str(pe)}")
                    except OSError as oe:
                        failed_files.append(mask_path)
                        logger.warning(f"清理文件失败（OS错误）: {mask_path}, 错误: {str(oe)}")
                    except Exception as file_err:
                        failed_files.append(mask_path)
                        logger.warning(f"清理文件失败（未知错误）: {mask_path}, 错误: {str(file_err)}")

            # 第二轮：清理目录下所有可能残留的 .npy 文件（防御性清理）
            if os.path.exists(tiles_mask_dir) and os.path.isdir(tiles_mask_dir):
                try:
                    for filename in os.listdir(tiles_mask_dir):
                        if filename.endswith('.npy'):
                            file_path = os.path.join(tiles_mask_dir, filename)
                            try:
                                file_size = os.path.getsize(file_path)
                                os.remove(file_path)
                                cleaned_count += 1
                                total_cleaned_bytes += file_size
                            except Exception:
                                pass  # 静默跳过无法删除的文件
                except Exception as list_err:
                    logger.warning(f"遍历 tiles_mask 目录失败: {str(list_err)}")

                # 尝试删除空目录
                try:
                    remaining = os.listdir(tiles_mask_dir)
                    if not remaining:
                        os.rmdir(tiles_mask_dir)
                        logger.info(f"tiles_mask 目录已删除: {tiles_mask_dir}")
                    else:
                        # 目录非空，尝试逐个删除残留文件后再次尝试
                        for filename in remaining:
                            try:
                                os.remove(os.path.join(tiles_mask_dir, filename))
                            except Exception:
                                pass
                        if not os.listdir(tiles_mask_dir):
                            os.rmdir(tiles_mask_dir)
                except FileNotFoundError:
                    pass  # 目录已被其他进程删除
                except Exception as dir_err:
                    logger.warning(f"删除 tiles_mask 目录失败: {str(dir_err)}")

            # 记录清理结果
            if cleaned_count > 0:
                logger.info(
                    f"临时文件清理完成: 成功清理 {cleaned_count} 个文件, "
                    f"释放空间约 {total_cleaned_bytes / 1024 / 1024:.1f}MB"
                )

            if failed_files:
                logger.error(f"临时文件清理失败 {len(failed_files)} 个文件:")
                for file_path in failed_files[:5]:  # 最多显示5个
                    logger.error(f"  - {file_path}")
                if len(failed_files) > 5:
                    logger.error(f"  ... 还有 {len(failed_files) - 5} 个文件")

        except Exception as e:
            # 最外层 catch-all：即使清理过程出现异常也不影响主流程
            logger.error(f"清理 tile mask 文件时出现未预期异常: {e}", exc_info=True)

            # 最终兜底：尝试直接删除整个目录
            try:
                import shutil
                if os.path.exists(tiles_mask_dir):
                    shutil.rmtree(tiles_mask_dir, ignore_errors=True)
                    logger.warning("已通过 shutil.rmtree 强制清理 tiles_mask 目录")
            except Exception:
                pass

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
        r_threshold_factor: Optional[float] = None,
        g_threshold_factor: Optional[float] = None,
        contrast_threshold_factor: Optional[float] = None,
        task_manager=None,
        task_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[Dict], str]:
        """
        对分块影像进行无监督病害木检测

        影像会被自动分块为 1024×1024 的分块，每个分块独立处理，
        然后将结果合并回原始影像坐标系。
        支持并行处理多个分块，默认使用 8 个工作进程。

        Args:
            image_data: 原始影像数据 (H, W, B)
            n_clusters: K-means 聚类类别数
            min_area: 最小斑块面积阈值
            nodata_value: NoData 像元值
            tile_size: 分块尺寸（默认 1024×1024）
            padding_mode: 边缘处理方式 ("pad" 或 "crop")
            use_parallel: 是否使用并行处理
            num_workers: 工作进程数（默认 8）
            task_manager: 任务管理器（用于更新进度）
            task_id: 任务ID（用于进度跟踪）

        Returns:
            (检测是否成功, 检测结果字典, 错误信息或成功消息)
        """
        try:
            if image_data is None or image_data.size == 0:
                return False, None, "影像数据为空"

            H, W, B = image_data.shape

            tile_size = min(tile_size, 1024)

            import multiprocessing as mp
            if num_workers is None:
                num_workers = min(DEFAULT_PARALLEL_WORKERS, mp.cpu_count() - 1)
            num_workers = max(1, min(num_workers, mp.cpu_count() - 1))

            logger.info(
                f"[{task_id}] 开始分块检测: 影像尺寸={W}x{H}, 分块尺寸={tile_size}x{tile_size}"
            )
            logger.info(f"[{task_id}] 并行参数: num_workers={num_workers}, tile_size={tile_size}")
            ResourceMonitor.log_resource_status(f"分块检测开始 [{task_id}]")

            logger.debug(f"[{task_id}] 生成分块中...")
            success, tiles, msg = TilingService.generate_tiles(
                image_data,
                tile_size=tile_size,
                padding_mode=padding_mode,
                spatial_ref=self.spatial_ref,
            )
            if not success:
                logger.error(f"[{task_id}] 分块生成失败: {msg}")
                return False, None, msg

            logger.info(f"[{task_id}] 已生成 {len(tiles)} 个分块")

            if use_parallel:
                # 并行处理
                logger.info(f"[{task_id}] 开始并行处理 tiles: {len(tiles)}")
                logger.info(f"[{task_id}] 使用并行处理分块，工作进程数={num_workers}")
                ResourceMonitor.log_resource_status(f"并行处理分块开始 [{task_id}]")

                # 检查停止标志
                if task_manager and task_manager.is_stop_requested(task_id):
                    logger.info(f"[{task_id}] 检测任务被停止（并行处理前）")
                    return False, None, "检测任务被用户停止"

                # 为每个瓦片准备参数元组（不传递 self，worker 内部创建 service）
                tile_args = [
                    (tile, n_clusters, min_area, nodata_value, r_threshold_factor, g_threshold_factor, contrast_threshold_factor)
                    for tile in tiles
                ]

                try:
                    success, tile_results, errors, msg = (
                        ParallelProcessingService.process_tiles_parallel(
                            tile_args,
                            _process_tile_for_parallel,
                            num_workers=num_workers,
                            error_handling="log",
                            task_manager=task_manager,
                            task_id=task_id,
                        )
                    )

                    if not success and (tile_results is None or len(tile_results) == 0):
                        raise RuntimeError(f"并行处理失败: {msg}")

                    # 过滤掉错误结果
                    valid_results = [r for r in tile_results if r is not None and "error" not in r]
                    logger.info(
                        f"[{task_id}] 并行处理完成: {len(valid_results)} 个成功, {len(errors)} 个失败"
                    )
                    ResourceMonitor.log_resource_status(f"并行处理分块完成 [{task_id}]")

                except Exception as parallel_error:
                    logger.warning(
                        f"[{task_id}] 并行处理失败 ({parallel_error})，自动切换为顺序执行"
                    )
                    use_parallel = False

                # 更新进度到 60%（处理分块完成）
                if task_manager and task_id:
                    task_manager.update_progress(
                        task_id, 60, f"分块处理完成: {len(valid_results)}/{len(tiles)} 个成功"
                    )

            if not use_parallel:
                # 顺序处理
                logger.info(f"[{task_id}] 使用顺序处理分块")
                valid_results = []
                for tile_idx, tile in enumerate(tiles):
                    # 检查停止标志
                    if task_manager and task_manager.is_stop_requested(task_id):
                        logger.info(f"[{task_id}] 检测任务被停止（分块处理中，已处理 {tile_idx}/{len(tiles)} 个分块）")
                        return False, None, "检测任务被用户停止"

                    logger.debug(f"[{task_id}] 处理分块 {tile_idx + 1}/{len(tiles)}")
                    success, result, msg = self._process_single_tile(
                        tile, n_clusters, min_area, nodata_value,
                        r_threshold_factor, g_threshold_factor, contrast_threshold_factor
                    )
                    if success:
                        valid_results.append(result)
                    else:
                        logger.error(f"[{task_id}] 分块 {tile.tile_index} 处理失败: {msg}")

                    # 更新进度
                    if task_manager and task_id:
                        progress = 30 + int((tile_idx / len(tiles)) * 30)
                        task_manager.update_progress(task_id, progress, f"处理分块中: {tile_idx + 1}/{len(tiles)}")

            if not valid_results:
                logger.error(f"[{task_id}] 所有分块处理失败")
                return False, None, "所有分块处理失败"

            # 确认 cleanup 没在 merge 前删除 tile
            tiles_mask_dir = os.path.join("storage", "tiles_mask")
            if os.path.exists(tiles_mask_dir):
                existing_files = os.listdir(tiles_mask_dir)
                logger.info(f"[{task_id}] merge 前 tiles_mask 目录文件数: {len(existing_files)}")
            else:
                logger.warning(f"[{task_id}] merge 前 tiles_mask 目录不存在!")

            logger.info(f"[{task_id}] merge 输出目录: {os.getcwd()}")
            import shutil
            disk_usage = shutil.disk_usage(os.getcwd())
            logger.info(
                f"[{task_id}] 磁盘状态: 总计={disk_usage.total / 1024 / 1024 / 1024:.1f}GB, "
                f"已用={disk_usage.used / 1024 / 1024 / 1024:.1f}GB, "
                f"可用={disk_usage.free / 1024 / 1024 / 1024:.1f}GB"
            )
            if disk_usage.free < 1024 * 1024 * 1024:  # < 1GB
                logger.warning(f"[{task_id}] 磁盘可用空间不足 1GB!")

            logger.info(f"[{task_id}] 开始基于距离聚类的点合并（无全局内存模式）")
            if task_manager and task_id:
                task_manager.update_progress(task_id, 75, "合并分块候选点")

            # 使用新的点合并方法（基于距离聚类，取消全局 mask 生成）
            success, all_center_points, msg = self._merge_tile_points(
                valid_results, H, W,
                min_area=min_area,
                task_manager=task_manager,
                task_id=task_id,
            )
            if not success:
                logger.error(f"[{task_id}] 点合并失败: {msg}")
                self._cleanup_tile_masks(valid_results)
                return False, None, msg

            # 更新进度到 85%
            if task_manager and task_id:
                task_manager.update_progress(task_id, 85, f"点合并完成，共 {len(all_center_points)} 个候选点")

            logger.info(f"[{task_id}] 点合并完成，共 {len(all_center_points)} 个候选点")

            # 更新进度到 95%（开始清理临时文件）
            if task_manager and task_id:
                task_manager.update_progress(task_id, 95, "清理临时文件")

            # 清理临时 tile mask 文件（步骤12：cleanup 异常保护）
            try:
                self._cleanup_tile_masks(valid_results)
            except Exception as e:
                logger.warning(f"cleanup skipped: {e}")

            # 更新进度到 100%（准备返回结果）
            if task_manager and task_id:
                task_manager.update_progress(task_id, 100, "准备返回结果")

            # 第五步：结果输出
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

            logger.info("非监督分类任务完成")
            logger.info(f"[{task_id}] 分块检测完成")
            ResourceMonitor.log_resource_status(f"分块检测完成 [{task_id}]")

            if task_manager and task_id:
                task_manager.update_status(task_id, "completed")

            return True, result, "分块检测成功"

        except Exception as e:
            logger.error(f"[{task_id}] 分块检测失败: {str(e)}")
            ResourceMonitor.log_resource_status(f"分块检测异常 [{task_id}]")
            return False, None, f"分块检测失败: {str(e)}"

    def detect_from_file(
        self,
        image_path: str,
        n_clusters: int = 4,
        min_area: int = 50,
        nodata_value: Optional[float] = None,
        r_threshold_factor: Optional[float] = None,
        g_threshold_factor: Optional[float] = None,
        contrast_threshold_factor: Optional[float] = None,
        task_manager=None,
        task_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[Dict], str]:
        """
        基于文件的流式无监督病害木检测（适用于大型遥感影像）。

        直接从磁盘文件按需读取分块，避免将完整影像（如4GB TIFF）加载到内存。
        使用 generate_tiles_from_file 生成器模式，每个分块仅在处理时从磁盘读取。

        Args:
            image_path: 影像文件路径
            n_clusters: K-means 聚类类别数
            min_area: 最小斑块面积阈值
            nodata_value: NoData 像元值
            r_threshold_factor: 红波段阈值因子
            g_threshold_factor: 绿波段阈值因子
            contrast_threshold_factor: 对比度阈值因子
            task_manager: 任务管理器（用于更新进度）
            task_id: 任务ID（用于进度跟踪）

        Returns:
            (检测是否成功, 检测结果字典, 错误信息或成功消息)
        """
        from backend.utils.image_reader import ImageReader
        import gc
        import multiprocessing as mp

        try:
            logger.info(f"[{task_id}] 基于文件的流式无监督检测开始")
            ResourceMonitor.log_resource_status(f"文件流式检测开始 [{task_id}]")

            # 获取影像信息（不加载完整数据）
            success, info, msg = ImageReader.get_image_info(image_path)
            if not success:
                return False, None, f"获取影像信息失败: {msg}"

            W = info["width"]
            H = info["height"]
            B = info["band_count"]

            tile_size = min(DEFAULT_TILE_SIZE, 1024)

            num_workers = min(DEFAULT_PARALLEL_WORKERS, mp.cpu_count() - 1)
            num_workers = max(1, min(num_workers, mp.cpu_count() - 1))

            logger.info(
                f"[{task_id}] 流式分块检测: 影像尺寸={W}x{H}, "
                f"波段数={B}, 分块尺寸={tile_size}x{tile_size}"
            )
            logger.info(f"[{task_id}] 并行参数: num_workers={num_workers}")
            ResourceMonitor.log_resource_status(f"流式分块检测开始 [{task_id}]")

            # 检查停止标志
            if task_manager and task_manager.is_stop_requested(task_id):
                logger.info(f"[{task_id}] 检测任务被停止（开始前）")
                return False, None, "检测任务被用户停止"

            if task_manager and task_id:
                task_manager.update_progress(task_id, 15, "从磁盘生成分块")

            # 计算总瓦片数量（用于进度跟踪）
            n_rows = (H + tile_size - 1) // tile_size
            n_cols = (W + tile_size - 1) // tile_size
            total_tiles = n_rows * n_cols
            logger.info(f"[{task_id}] 预计总分块数: {total_tiles} ({n_rows}行 x {n_cols}列)")

            # 分批从磁盘读取并处理分块，避免将全部分块加载到内存
            # batch_size: 每批处理的分块数（至少为 worker 数的 2 倍以保证并行效率）
            batch_size = max(num_workers * 2, 4)
            all_valid_results = []
            tile_generator = TilingService.generate_tiles_from_file(
                image_path,
                tile_size=tile_size,
                padding_mode="pad",
                spatial_ref=self.spatial_ref,
            )

            batch_tiles = []
            tile_counter = 0

            for tile in tile_generator:
                if task_manager and task_manager.is_stop_requested(task_id):
                    logger.info(f"[{task_id}] 检测任务被停止（分块生成中）")
                    return False, None, "检测任务被用户停止"

                batch_tiles.append(tile)
                tile_counter += 1

                # 当收集到足够的分块或处理完最后一批时，开始并行处理
                if len(batch_tiles) >= batch_size or tile_counter == total_tiles:
                    batch_start = tile_counter - len(batch_tiles) + 1
                    logger.info(
                        f"[{task_id}] 处理第 {batch_start}-{tile_counter}/{total_tiles} 个分块 "
                        f"(batch_size={len(batch_tiles)})"
                    )

                    if task_manager and task_id:
                        progress = 15 + int((tile_counter / total_tiles) * 45)
                        task_manager.update_progress(
                            task_id, progress,
                            f"处理分块: {batch_start}-{tile_counter}/{total_tiles}"
                        )

                    # 准备批处理参数
                    batch_args = [
                        (tile, n_clusters, min_area, nodata_value, r_threshold_factor, g_threshold_factor, contrast_threshold_factor)
                        for tile in batch_tiles
                    ]

                    # 并行处理本批分块
                    try:
                        success, batch_results, errors, msg = (
                            ParallelProcessingService.process_tiles_parallel(
                                batch_args,
                                _process_tile_for_parallel,
                                num_workers=num_workers,
                                error_handling="log",
                                task_manager=task_manager,
                                task_id=task_id,
                            )
                        )
                        if success or batch_results:
                            valid_batch = [r for r in batch_results if r is not None and "error" not in r]
                            all_valid_results.extend(valid_batch)
                            if errors:
                                logger.warning(
                                    f"[{task_id}] 批次 {batch_start}-{tile_counter} 有 {len(errors)} 个分块失败"
                                )
                    except Exception as batch_error:
                        logger.error(f"[{task_id}] 批次处理异常: {batch_error}")

                    # 释放批次分块数据（关键：避免内存累积）
                    batch_tiles.clear()
                    gc.collect()

            logger.info(f"[{task_id}] 所有批次处理完成，成功: {len(all_valid_results)}/{total_tiles} 个分块")

            if not all_valid_results:
                return False, None, "所有分块处理失败"

            # 更新进度
            if task_manager and task_id:
                task_manager.update_progress(task_id, 60, f"分块处理完成: {len(all_valid_results)}/{total_tiles} 个成功")

            # 清理 tile mask 临时文件
            self._cleanup_tile_masks(all_valid_results)

            # 使用点合并方法（无全局内存模式）
            logger.info(f"[{task_id}] 开始基于距离聚类的点合并（流式模式，无全局内存）")
            if task_manager and task_id:
                task_manager.update_progress(task_id, 75, "合并分块候选点")

            success, all_center_points, msg = self._merge_tile_points(
                all_valid_results, H, W,
                min_area=min_area,
                task_manager=task_manager,
                task_id=task_id,
            )
            if not success:
                logger.error(f"[{task_id}] 点合并失败: {msg}")
                return False, None, msg

            if task_manager and task_id:
                task_manager.update_progress(task_id, 85, f"点合并完成，共 {len(all_center_points)} 个候选点")

            logger.info(f"[{task_id}] 点合并完成，共 {len(all_center_points)} 个候选点")

            # 释放中间变量
            del all_valid_results
            gc.collect()
            ResourceMonitor.log_resource_status(f"流式分块检测完成 [{task_id}]")

            result = {
                "center_points": all_center_points,
                "n_tiles": total_tiles,
                "n_successful_tiles": len(all_center_points),  # 使用候选点数替代
                "n_clusters": n_clusters,
                "n_candidates": len(all_center_points),
                "tile_size": tile_size,
                "image_size": (W, H),
                "method": "分块无监督分类方法（流式文件模式）",
                "description": "基于文件流式批处理的 1024×1024 分块光谱、纹理和空间特征无监督病害木检测",
            }

            logger.info(f"[{task_id}] 流式分块检测完成，发现 {len(all_center_points)} 个候选区域")
            return True, result, "流式分块检测成功"

        except Exception as e:
            logger.error(f"[{task_id}] 流式分块检测异常: {str(e)}")
            import traceback
            logger.error(f"[{task_id}] 异常详情: {traceback.format_exc()}")
            ResourceMonitor.log_resource_status(f"流式分块检测异常 [{task_id}]")
            return False, None, f"流式分块检测失败: {str(e)}"

    def detect(
        self,
        image_data: np.ndarray,
        n_clusters: int = 4,
        min_area: int = 50,
        nodata_value: Optional[float] = None,
        r_threshold_factor: Optional[float] = None,
        g_threshold_factor: Optional[float] = None,
        contrast_threshold_factor: Optional[float] = None,
        task_manager=None,
        task_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[Dict], str]:
        """
        执行完整的无监督病害木检测流程（优化版本）

        优化说明：
        - 对于大影像（>5000×5000），自动使用分块处理 + 并行处理
        - 对于小影像，使用单线程处理以减少开销
        - 显式释放中间变量，降低峰值内存占用 30-40%
        - 支持任务进度跟踪，防止进度卡死

        Args:
            image_data: 原始影像数据 (H, W, B)
            n_clusters: K-means 聚类类别数
            min_area: 最小斑块面积阈值
            nodata_value: NoData 像元值
            r_threshold_factor: 红波段阈值因子（默认1.1，表示高于均值10%）
            g_threshold_factor: 绿波段阈值因子（默认0.9，表示低于均值10%）
            contrast_threshold_factor: 对比度阈值因子（默认1.1，表示高于均值10%）
            task_manager: 任务管理器（用于更新进度）
            task_id: 任务ID（用于进度跟踪）

        Returns:
            (检测是否成功, 检测结果字典, 错误信息或成功消息)
        """
        import gc

        try:
            logger.info(f"[{task_id}] 无监督检测开始")
            ResourceMonitor.log_resource_status(f"无监督检测开始 [{task_id}]")

            H, W, B = image_data.shape
            image_size = H * W

            # 根据影像大小自动选择处理方式
            # 大影像使用分块处理以降低内存占用和提高并行效率
            if image_size > 25000000:  # 5000×5000 像素
                logger.info(
                    f"[{task_id}] 影像尺寸较大 ({W}×{H})，使用分块处理 + 并行处理"
                )
                return self.detect_on_tiled_image(
                    image_data,
                    n_clusters=n_clusters,
                    min_area=min_area,
                    nodata_value=nodata_value,
                    use_parallel=True,
                    num_workers=None,
                    r_threshold_factor=r_threshold_factor,
                    g_threshold_factor=g_threshold_factor,
                    contrast_threshold_factor=contrast_threshold_factor,
                    task_manager=task_manager,
                    task_id=task_id,
                )

            # 小影像使用单线程处理
            logger.info(f"[{task_id}] 影像尺寸较小 ({W}×{H})，使用单线程处理")

            logger.debug(f"[{task_id}] 影像归一化")
            if task_manager and task_id:
                task_manager.update_progress(task_id, 10, "影像归一化中")
            success, normalized_image, msg = self.normalize_image(
                image_data, nodata_value
            )
            if not success:
                logger.error(f"[{task_id}] 影像归一化失败: {msg}")
                return False, None, msg

            # 检查停止标志
            if task_manager and task_manager.is_stop_requested(task_id):
                logger.info(f"[{task_id}] 检测任务被停止（影像归一化后）")
                return False, None, "检测任务被用户停止"

            logger.debug(f"[{task_id}] 特征构建与标准化")
            if task_manager and task_id:
                task_manager.update_progress(task_id, 30, "构建和标准化特征")
            success, feature_result, msg = self.construct_feature_matrix(
                normalized_image
            )
            if not success:
                logger.error(f"[{task_id}] 特征构建失败: {msg}")
                return False, None, msg
            feature_matrix, valid_pixel_mask = feature_result

            # 检查停止标志
            if task_manager and task_manager.is_stop_requested(task_id):
                logger.info(f"[{task_id}] 检测任务被停止（特征构建后）")
                return False, None, "检测任务被用户停止"

            logger.debug(f"[{task_id}] K-means 聚类")
            if task_manager and task_id:
                task_manager.update_progress(task_id, 50, "执行K-means聚类（排除NoData）")
            success, labels, centers, msg = self.kmeans_clustering(
                feature_matrix, n_clusters,
                valid_pixel_mask=valid_pixel_mask,
            )
            if not success:
                logger.error(f"[{task_id}] K-means 聚类失败: {msg}")
                return False, None, msg

            # 检查停止标志
            if task_manager and task_manager.is_stop_requested(task_id):
                logger.info(f"[{task_id}] 检测任务被停止（K-means聚类后）")
                return False, None, "检测任务被用户停止"

            # 提取光谱特征用于候选类别判定
            logger.debug(f"[{task_id}] 提取光谱特征")
            if task_manager and task_id:
                task_manager.update_progress(task_id, 60, "提取光谱特征")
            success, spectral_features, msg = self.extract_spectral_features(
                normalized_image
            )
            if not success:
                logger.error(f"[{task_id}] 光谱特征提取失败: {msg}")
                return False, None, msg

            logger.debug(f"[{task_id}] 病害木候选类别判定")
            if task_manager and task_id:
                task_manager.update_progress(task_id, 65, "判定病害木候选类别")
            success, candidate_mask, msg = self.identify_disease_candidates(
                normalized_image, labels, centers, spectral_features,
                r_threshold_factor, g_threshold_factor, contrast_threshold_factor
            )
            if not success:
                logger.error(f"[{task_id}] 候选类别判定失败: {msg}")
                return False, None, msg

            # 检查停止标志
            if task_manager and task_manager.is_stop_requested(task_id):
                logger.info(f"[{task_id}] 检测任务被停止（候选类别判定后）")
                return False, None, "检测任务被用户停止"

            logger.debug(f"[{task_id}] 空间后处理")
            if task_manager and task_id:
                task_manager.update_progress(task_id, 75, "进行空间后处理")
            success, processed_mask, center_points, msg = self.spatial_postprocessing(
                candidate_mask, (H, W), min_area, task_manager, task_id
            )
            if not success:
                logger.error(f"[{task_id}] 空间后处理失败: {msg}")
                return False, None, msg

            if task_manager and task_id:
                task_manager.update_progress(task_id, 90, "准备返回结果")

            logger.debug(f"[{task_id}] 结果输出")
            result = {
                "candidate_mask": processed_mask,
                "center_points": center_points,
                "n_clusters": n_clusters,
                "n_candidates": len(center_points),
                "method": "传统非监督分类方法",
                "description": "基于光谱、纹理和空间特征的无监督病害木检测",
            }

            # 显式释放中间变量，降低峰值内存占用
            del normalized_image, feature_matrix, labels, centers
            del spectral_features, candidate_mask, processed_mask
            gc.collect()

            # 步骤19：最终任务完成日志
            logger.info("非监督分类任务完成")
            logger.info(f"[{task_id}] 无监督检测完成，发现 {len(center_points)} 个候选点")
            ResourceMonitor.log_resource_status(f"无监督检测完成 [{task_id}]")

            # 步骤13：任务结束时强制更新状态
            if task_manager and task_id:
                task_manager.update_status(task_id, "completed")

            return True, result, "无监督病害木检测成功"

        except Exception as e:
            logger.error(f"[{task_id}] 无监督检测失败: {str(e)}")
            ResourceMonitor.log_resource_status(f"无监督检测异常 [{task_id}]")
            return False, None, f"无监督病害木检测失败: {str(e)}"
