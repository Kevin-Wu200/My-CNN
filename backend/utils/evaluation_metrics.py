"""
评估指标工具模块
用于计算模型性能指标
"""

import numpy as np
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class EvaluationMetrics:
    """评估指标计算工具类"""

    @staticmethod
    def compute_accuracy(predictions: np.ndarray, labels: np.ndarray) -> float:
        """
        计算准确率

        Args:
            predictions: 预测标签数组
            labels: 真实标签数组

        Returns:
            准确率
        """
        if len(predictions) == 0:
            return 0.0

        correct = np.sum(predictions == labels)
        accuracy = correct / len(labels)

        return accuracy

    @staticmethod
    def compute_precision(predictions: np.ndarray, labels: np.ndarray) -> float:
        """
        计算精度（正样本预测正确率）

        Args:
            predictions: 预测标签数组
            labels: 真实标签数组

        Returns:
            精度
        """
        # 预测为正样本的数量
        predicted_positive = np.sum(predictions == 1)

        if predicted_positive == 0:
            return 0.0

        # 预测正确的正样本数量
        true_positive = np.sum((predictions == 1) & (labels == 1))

        precision = true_positive / predicted_positive

        return precision

    @staticmethod
    def compute_recall(predictions: np.ndarray, labels: np.ndarray) -> float:
        """
        计算召回率（正样本召回率）

        Args:
            predictions: 预测标签数组
            labels: 真实标签数组

        Returns:
            召回率
        """
        # 真实正样本数量
        actual_positive = np.sum(labels == 1)

        if actual_positive == 0:
            return 0.0

        # 预测正确的正样本数量
        true_positive = np.sum((predictions == 1) & (labels == 1))

        recall = true_positive / actual_positive

        return recall

    @staticmethod
    def compute_f1_score(predictions: np.ndarray, labels: np.ndarray) -> float:
        """
        计算 F1 值

        Args:
            predictions: 预测标签数组
            labels: 真实标签数组

        Returns:
            F1 值
        """
        precision = EvaluationMetrics.compute_precision(predictions, labels)
        recall = EvaluationMetrics.compute_recall(predictions, labels)

        if precision + recall == 0:
            return 0.0

        f1_score = 2 * (precision * recall) / (precision + recall)

        return f1_score

    @staticmethod
    def compute_confusion_matrix(
        predictions: np.ndarray, labels: np.ndarray
    ) -> np.ndarray:
        """
        计算混淆矩阵

        Args:
            predictions: 预测标签数组
            labels: 真实标签数组

        Returns:
            混淆矩阵 (2x2)
        """
        # 获取唯一的类别
        classes = np.unique(np.concatenate([predictions, labels]))

        # 初始化混淆矩阵
        confusion_matrix = np.zeros((len(classes), len(classes)), dtype=np.int32)

        # 填充混淆矩阵
        for i, true_class in enumerate(classes):
            for j, pred_class in enumerate(classes):
                confusion_matrix[i, j] = np.sum(
                    (labels == true_class) & (predictions == pred_class)
                )

        return confusion_matrix

    @staticmethod
    def compute_all_metrics(
        predictions: np.ndarray, labels: np.ndarray
    ) -> Dict[str, float]:
        """
        计算所有评估指标

        Args:
            predictions: 预测标签数组
            labels: 真实标签数组

        Returns:
            包含所有指标的字典
        """
        metrics = {
            "accuracy": EvaluationMetrics.compute_accuracy(predictions, labels),
            "precision": EvaluationMetrics.compute_precision(predictions, labels),
            "recall": EvaluationMetrics.compute_recall(predictions, labels),
            "f1_score": EvaluationMetrics.compute_f1_score(predictions, labels),
        }

        return metrics

    @staticmethod
    def format_metrics(metrics: Dict[str, float]) -> str:
        """
        格式化指标为字符串

        Args:
            metrics: 指标字典

        Returns:
            格式化后的字符串
        """
        lines = []
        for key, value in metrics.items():
            lines.append(f"{key}: {value:.4f}")

        return ", ".join(lines)
