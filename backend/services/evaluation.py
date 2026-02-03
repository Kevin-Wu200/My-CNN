"""
模型评估服务模块
用于实现模型性能评估和结果对比分析
"""

import numpy as np
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

from backend.utils.evaluation_metrics import EvaluationMetrics

logger = logging.getLogger(__name__)


class EvaluationService:
    """模型评估服务类"""

    @staticmethod
    def evaluate_model(
        predictions: np.ndarray,
        labels: np.ndarray,
    ) -> Dict[str, float]:
        """
        评估模型性能

        Args:
            predictions: 预测标签数组
            labels: 真实标签数组

        Returns:
            包含所有评估指标的字典
        """
        try:
            if len(predictions) == 0 or len(labels) == 0:
                return {}

            # 计算所有指标
            metrics = EvaluationMetrics.compute_all_metrics(predictions, labels)

            # 计算混淆矩阵
            confusion_matrix = EvaluationMetrics.compute_confusion_matrix(
                predictions, labels
            )

            # 添加混淆矩阵到结果
            metrics["confusion_matrix"] = confusion_matrix.tolist()

            logger.info(f"模型评估完成: {EvaluationMetrics.format_metrics(metrics)}")

            return metrics

        except Exception as e:
            logger.error(f"模型评估失败: {str(e)}")
            return {}

    @staticmethod
    def compare_models(
        results_list: List[Dict],
    ) -> Dict[str, any]:
        """
        对比多个模型的性能

        Args:
            results_list: 模型评估结果列表，每个元素包含：
                - model_name: 模型名称
                - predictions: 预测结果
                - labels: 真实标签

        Returns:
            对比分析结果字典
        """
        try:
            if not results_list:
                return {}

            comparison_results = {
                "num_models": len(results_list),
                "models": [],
                "best_model": None,
                "best_metric": None,
            }

            best_f1 = -1
            best_model_idx = -1

            for idx, result in enumerate(results_list):
                model_name = result.get("model_name", f"Model_{idx}")
                predictions = result.get("predictions")
                labels = result.get("labels")

                if predictions is None or labels is None:
                    logger.warning(f"模型 {model_name} 缺少预测或标签数据")
                    continue

                # 评估模型
                metrics = EvaluationService.evaluate_model(predictions, labels)

                model_result = {
                    "model_name": model_name,
                    "metrics": metrics,
                }

                comparison_results["models"].append(model_result)

                # 找出最佳模型
                f1_score = metrics.get("f1_score", 0)
                if f1_score > best_f1:
                    best_f1 = f1_score
                    best_model_idx = idx

            # 设置最佳模型
            if best_model_idx >= 0:
                comparison_results["best_model"] = comparison_results["models"][
                    best_model_idx
                ]["model_name"]
                comparison_results["best_metric"] = best_f1

            logger.info(
                f"模型对比完成: 共 {len(results_list)} 个模型, 最佳模型: {comparison_results['best_model']}"
            )

            return comparison_results

        except Exception as e:
            logger.error(f"模型对比失败: {str(e)}")
            return {}

    @staticmethod
    def generate_evaluation_report(
        model_name: str,
        metrics: Dict[str, float],
        output_path: str,
    ) -> Tuple[bool, str]:
        """
        生成评估报告

        Args:
            model_name: 模型名称
            metrics: 评估指标字典
            output_path: 输出文件路径

        Returns:
            (生成是否成功, 错误信息或成功消息)
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # 构建报告内容
            report = {
                "model_name": model_name,
                "evaluation_metrics": metrics,
                "summary": {
                    "accuracy": f"{metrics.get('accuracy', 0):.4f}",
                    "precision": f"{metrics.get('precision', 0):.4f}",
                    "recall": f"{metrics.get('recall', 0):.4f}",
                    "f1_score": f"{metrics.get('f1_score', 0):.4f}",
                },
            }

            # 写入 JSON 文件
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            logger.info(f"评估报告已生成: {output_path}")

            return True, f"报告生成成功: {output_path}"

        except Exception as e:
            logger.error(f"生成评估报告失败: {str(e)}")
            return False, f"报告生成失败: {str(e)}"

    @staticmethod
    def analyze_model_performance(
        metrics: Dict[str, float],
    ) -> Dict[str, str]:
        """
        分析模型性能

        Args:
            metrics: 评估指标字典

        Returns:
            性能分析结果字典
        """
        analysis = {}

        # 分析准确率
        accuracy = metrics.get("accuracy", 0)
        if accuracy >= 0.9:
            analysis["accuracy_level"] = "优秀"
        elif accuracy >= 0.8:
            analysis["accuracy_level"] = "良好"
        elif accuracy >= 0.7:
            analysis["accuracy_level"] = "中等"
        else:
            analysis["accuracy_level"] = "需要改进"

        # 分析精度和召回率的平衡
        precision = metrics.get("precision", 0)
        recall = metrics.get("recall", 0)

        if abs(precision - recall) < 0.05:
            analysis["balance"] = "精度和召回率平衡良好"
        elif precision > recall:
            analysis["balance"] = "精度高于召回率，可能存在假负例"
        else:
            analysis["balance"] = "召回率高于精度，可能存在假正例"

        # 分析 F1 值
        f1_score = metrics.get("f1_score", 0)
        if f1_score >= 0.85:
            analysis["f1_level"] = "优秀"
        elif f1_score >= 0.75:
            analysis["f1_level"] = "良好"
        elif f1_score >= 0.65:
            analysis["f1_level"] = "中等"
        else:
            analysis["f1_level"] = "需要改进"

        return analysis

    @staticmethod
    def export_results_for_visualization(
        metrics: Dict[str, float],
        output_path: str,
    ) -> Tuple[bool, str]:
        """
        导出结果用于可视化

        Args:
            metrics: 评估指标字典
            output_path: 输出文件路径

        Returns:
            (导出是否成功, 错误信息或成功消息)
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # 构建可视化数据
            visualization_data = {
                "metrics": {
                    "accuracy": metrics.get("accuracy", 0),
                    "precision": metrics.get("precision", 0),
                    "recall": metrics.get("recall", 0),
                    "f1_score": metrics.get("f1_score", 0),
                },
                "confusion_matrix": metrics.get("confusion_matrix", []),
            }

            # 写入 JSON 文件
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(visualization_data, f, indent=2, ensure_ascii=False)

            logger.info(f"可视化数据已导出: {output_path}")

            return True, f"导出成功: {output_path}"

        except Exception as e:
            logger.error(f"导出可视化数据失败: {str(e)}")
            return False, f"导出失败: {str(e)}"
