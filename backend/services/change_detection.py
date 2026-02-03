"""
变化检测服务模块
用于检测多时相影像中的变化
"""

import numpy as np
from typing import Tuple, Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


class ChangeDetectionService:
    """变化检测服务类"""

    @staticmethod
    def difference_based_change_detection(
        image1: np.ndarray,
        image2: np.ndarray,
        threshold: float = 0.1,
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        基于影像差分的变化检测

        Args:
            image1: 第一个时相影像 (H, W, C)
            image2: 第二个时相影像 (H, W, C)
            threshold: 变化阈值

        Returns:
            (检测是否成功, 变化检测结果, 错误信息或成功消息)
        """
        try:
            if image1 is None or image2 is None:
                return False, None, "影像数据为空"

            if image1.shape != image2.shape:
                return False, None, "两个影像尺寸不一致"

            # 计算影像差分
            diff = np.abs(image1.astype(np.float32) - image2.astype(np.float32))

            # 计算每个像素的平均差分
            mean_diff = np.mean(diff, axis=2)

            # 归一化
            if np.max(mean_diff) > 0:
                mean_diff = mean_diff / np.max(mean_diff)

            # 生成变化检测结果（二值化）
            change_map = (mean_diff > threshold).astype(np.uint8)

            logger.info(
                f"基于差分的变化检测完成: 变化像素数={np.sum(change_map)}"
            )

            return True, change_map, "变化检测成功"

        except Exception as e:
            logger.error(f"变化检测失败: {str(e)}")
            return False, None, f"变化检测失败: {str(e)}"

    @staticmethod
    def feature_based_change_detection(
        features1: np.ndarray,
        features2: np.ndarray,
        threshold: float = 0.5,
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        基于深度学习特征的变化检测

        Args:
            features1: 第一个时相的特征 (N, D)
            features2: 第二个时相的特征 (N, D)
            threshold: 变化阈值

        Returns:
            (检测是否成功, 变化检测结果, 错误信息或成功消息)
        """
        try:
            if features1 is None or features2 is None:
                return False, None, "特征数据为空"

            if features1.shape != features2.shape:
                return False, None, "两个特征维度不一致"

            # 计算特征距离（欧氏距离）
            distances = np.sqrt(np.sum((features1 - features2) ** 2, axis=1))

            # 归一化
            if np.max(distances) > 0:
                distances = distances / np.max(distances)

            # 生成变化检测结果
            change_map = (distances > threshold).astype(np.uint8)

            logger.info(
                f"基于特征的变化检测完成: 变化样本数={np.sum(change_map)}"
            )

            return True, change_map, "变化检测成功"

        except Exception as e:
            logger.error(f"变化检测失败: {str(e)}")
            return False, None, f"变化检测失败: {str(e)}"

    @staticmethod
    def temporal_consistency_analysis(
        predictions_list: List[np.ndarray],
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        时序一致性分析

        分析多个时相的预测结果，找出一致的变化

        Args:
            predictions_list: 多个时相的预测结果列表

        Returns:
            (分析是否成功, 一致性分析结果, 错误信息或成功消息)
        """
        try:
            if not predictions_list or len(predictions_list) < 2:
                return False, None, "预测结果列表不足"

            # 计算所有预测的平均值
            mean_predictions = np.mean(predictions_list, axis=0)

            # 计算标准差
            std_predictions = np.std(predictions_list, axis=0)

            # 一致性分数（标准差越小，一致性越高）
            consistency_score = 1.0 - (std_predictions / (np.max(std_predictions) + 1e-6))

            logger.info(
                f"时序一致性分析完成: 平均一致性={np.mean(consistency_score):.4f}"
            )

            return True, consistency_score, "一致性分析成功"

        except Exception as e:
            logger.error(f"一致性分析失败: {str(e)}")
            return False, None, f"一致性分析失败: {str(e)}"
