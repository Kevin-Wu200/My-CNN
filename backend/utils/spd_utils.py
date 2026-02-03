"""
SPD 矩阵处理工具模块
用于处理对称正定矩阵和 Log-Euclidean 映射
"""

import numpy as np
import torch
import torch.nn as nn
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class SPDUtils:
    """SPD 矩阵处理工具类"""

    @staticmethod
    def compute_covariance_matrix(
        features: np.ndarray,
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        计算特征的协方差矩阵（SPD 矩阵）

        Args:
            features: 特征数组 (N, D)，N 为样本数，D 为特征维度

        Returns:
            (计算是否成功, 协方差矩阵, 错误信息或成功消息)
        """
        try:
            if features is None or features.size == 0:
                return False, None, "特征数组为空"

            # 计算协方差矩阵
            cov_matrix = np.cov(features.T)

            # 确保矩阵是 2D 的
            if cov_matrix.ndim == 0:
                cov_matrix = np.array([[cov_matrix]])
            elif cov_matrix.ndim == 1:
                cov_matrix = cov_matrix.reshape(1, -1)

            # 添加小的正则化项以确保正定性
            epsilon = 1e-6
            cov_matrix += epsilon * np.eye(cov_matrix.shape[0])

            return True, cov_matrix, "协方差矩阵计算成功"

        except Exception as e:
            logger.error(f"协方差矩阵计算失败: {str(e)}")
            return False, None, f"协方差矩阵计算失败: {str(e)}"

    @staticmethod
    def matrix_log(matrix: np.ndarray) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        计算矩阵的对数（Log-Euclidean 映射）

        Args:
            matrix: 输入矩阵

        Returns:
            (计算是否成功, 矩阵对数, 错误信息或成功消息)
        """
        try:
            if matrix is None or matrix.size == 0:
                return False, None, "矩阵为空"

            # 计算矩阵的特征值和特征向量
            eigenvalues, eigenvectors = np.linalg.eigh(matrix)

            # 确保特征值为正
            eigenvalues = np.maximum(eigenvalues, 1e-10)

            # 计算对数特征值
            log_eigenvalues = np.log(eigenvalues)

            # 重构矩阵对数
            log_matrix = eigenvectors @ np.diag(log_eigenvalues) @ eigenvectors.T

            return True, log_matrix, "矩阵对数计算成功"

        except Exception as e:
            logger.error(f"矩阵对数计算失败: {str(e)}")
            return False, None, f"矩阵对数计算失败: {str(e)}"

    @staticmethod
    def matrix_exp(matrix: np.ndarray) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        计算矩阵的指数（Log-Euclidean 逆映射）

        Args:
            matrix: 输入矩阵

        Returns:
            (计算是否成功, 矩阵指数, 错误信息或成功消息)
        """
        try:
            if matrix is None or matrix.size == 0:
                return False, None, "矩阵为空"

            # 计算矩阵的特征值和特征向量
            eigenvalues, eigenvectors = np.linalg.eigh(matrix)

            # 计算指数特征值
            exp_eigenvalues = np.exp(eigenvalues)

            # 重构矩阵指数
            exp_matrix = eigenvectors @ np.diag(exp_eigenvalues) @ eigenvectors.T

            return True, exp_matrix, "矩阵指数计算成功"

        except Exception as e:
            logger.error(f"矩阵指数计算失败: {str(e)}")
            return False, None, f"矩阵指数计算失败: {str(e)}"

    @staticmethod
    def tangent_space_projection(
        cov_matrix: np.ndarray,
        reference_matrix: Optional[np.ndarray] = None,
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        将 SPD 矩阵投影到切空间

        Args:
            cov_matrix: 协方差矩阵
            reference_matrix: 参考矩阵（默认为单位矩阵）

        Returns:
            (投影是否成功, 切空间中的矩阵, 错误信息或成功消息)
        """
        try:
            if cov_matrix is None or cov_matrix.size == 0:
                return False, None, "协方差矩阵为空"

            # 如果未指定参考矩阵，使用单位矩阵
            if reference_matrix is None:
                reference_matrix = np.eye(cov_matrix.shape[0])

            # 计算参考矩阵的平方根
            success, sqrt_ref, message = SPDUtils._matrix_sqrt(reference_matrix)
            if not success:
                return False, None, message

            # 计算参考矩阵平方根的逆
            inv_sqrt_ref = np.linalg.inv(sqrt_ref)

            # 投影到切空间
            projected = inv_sqrt_ref @ cov_matrix @ inv_sqrt_ref

            # 计算对数
            success, log_projected, message = SPDUtils.matrix_log(projected)
            if not success:
                return False, None, message

            return True, log_projected, "切空间投影成功"

        except Exception as e:
            logger.error(f"切空间投影失败: {str(e)}")
            return False, None, f"切空间投影失败: {str(e)}"

    @staticmethod
    def _matrix_sqrt(matrix: np.ndarray) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        计算矩阵的平方根

        Args:
            matrix: 输入矩阵

        Returns:
            (计算是否成功, 矩阵平方根, 错误信息或成功消息)
        """
        try:
            # 计算特征值和特征向量
            eigenvalues, eigenvectors = np.linalg.eigh(matrix)

            # 确保特征值为正
            eigenvalues = np.maximum(eigenvalues, 1e-10)

            # 计算平方根特征值
            sqrt_eigenvalues = np.sqrt(eigenvalues)

            # 重构矩阵平方根
            sqrt_matrix = eigenvectors @ np.diag(sqrt_eigenvalues) @ eigenvectors.T

            return True, sqrt_matrix, "矩阵平方根计算成功"

        except Exception as e:
            return False, None, f"矩阵平方根计算失败: {str(e)}"

    @staticmethod
    def flatten_tangent_space(
        tangent_matrix: np.ndarray,
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        将切空间中的矩阵展平为向量

        Args:
            tangent_matrix: 切空间中的矩阵

        Returns:
            (展平是否成功, 展平后的向量, 错误信息或成功消息)
        """
        try:
            if tangent_matrix is None or tangent_matrix.size == 0:
                return False, None, "矩阵为空"

            # 提取上三角部分（因为矩阵是对称的）
            triu_indices = np.triu_indices(tangent_matrix.shape[0])
            vector = tangent_matrix[triu_indices]

            return True, vector, "矩阵展平成功"

        except Exception as e:
            logger.error(f"矩阵展平失败: {str(e)}")
            return False, None, f"矩阵展平失败: {str(e)}"
