"""
模型训练服务模块
用于实现模型训练流程
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging
import json
import os
import time

from backend.utils.evaluation_metrics import EvaluationMetrics

logger = logging.getLogger(__name__)

# 模型文件大小限制（2GB）
MAX_MODEL_SIZE = 2 * 1024 * 1024 * 1024


class TrainingService:
    """模型训练服务类"""

    def __init__(
        self,
        model: nn.Module,
        device: str = "cpu",
        model_save_dir: Optional[Path] = None,
        model_config: Optional[Dict] = None,
    ):
        """
        初始化训练服务

        Args:
            model: 要训练的模型
            device: 计算设备（cpu 或 cuda）
            model_save_dir: 模型保存目录
            model_config: 模型配置字典（用于记录降维等配置信息）
        """
        self.model = model.to(device)
        self.device = device
        self.model_save_dir = model_save_dir or Path("./models")
        self.model_save_dir.mkdir(parents=True, exist_ok=True)
        self.model_config = model_config or {}

        # 记录降维配置
        if self.model_config.get("use_multidim_reduction"):
            logger.info(
                f"[MULTIDIM_REDUCTION] enabled=True, "
                f"reduction_factor={self.model_config.get('reduction_factor', 4)}, "
                f"final_channels={self.model_config.get('final_channels', 128)}, "
                f"attention={self.model_config.get('attention_type', 'se')}"
            )

        # 验证保存目录的写权限
        if not os.access(str(self.model_save_dir), os.W_OK):
            logger.warning(f"[SAVE_DIR_NOT_WRITABLE] path={self.model_save_dir}")

        # 训练历史记录
        self.training_history = {
            "train_loss": [],
            "train_accuracy": [],
            "val_loss": [],
            "val_accuracy": [],
            "val_precision": [],
            "val_recall": [],
            "val_f1": [],
        }

    @staticmethod
    def _validate_model_file(model_path: str) -> Tuple[bool, str]:
        """
        验证模型文件是否可以加载

        Args:
            model_path: 模型文件路径

        Returns:
            (验证是否通过, 错误信息)
        """
        try:
            file_path = Path(model_path)

            # 检查文件是否存在
            if not file_path.exists():
                return False, f"模型文件不存在: {model_path}"

            # 检查文件是否可读
            if not os.access(str(file_path), os.R_OK):
                return False, f"模型文件不可读（权限问题）: {model_path}"

            # 检查文件大小
            file_size = file_path.stat().st_size
            if file_size <= 0:
                return False, f"模型文件大小无效: {file_size} bytes"

            if file_size > MAX_MODEL_SIZE:
                return False, f"模型文件过大: {file_size} bytes (限制: {MAX_MODEL_SIZE} bytes)"

            logger.info(f"[MODEL_FILE_VALIDATION_PASS] filePath={model_path}, fileSize={file_size}")
            return True, ""

        except Exception as e:
            return False, f"模型文件验证失败: {str(e)}"

    def train_epoch(
        self,
        train_loader: DataLoader,
        optimizer: optim.Optimizer,
        criterion: nn.Module,
    ) -> Tuple[float, float]:
        """
        训练一个 epoch

        Args:
            train_loader: 训练数据加载器
            optimizer: 优化器
            criterion: 损失函数

        Returns:
            (平均损失, 准确率)
        """
        self.model.train()

        total_loss = 0.0
        total_correct = 0
        total_samples = 0

        for batch_idx, (inputs, labels) in enumerate(train_loader):
            # 将数据移到设备
            inputs = inputs.to(self.device)
            labels = labels.to(self.device)

            # 前向传播
            outputs = self.model(inputs)

            # 计算损失
            loss = criterion(outputs, labels)

            # 反向传播
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            # 记录损失
            total_loss += loss.item() * inputs.size(0)

            # 计算准确率
            _, predicted = torch.max(outputs.data, 1)
            total_correct += (predicted == labels).sum().item()
            total_samples += labels.size(0)

            # 打印进度
            if (batch_idx + 1) % 10 == 0:
                logger.info(
                    f"Batch [{batch_idx + 1}/{len(train_loader)}], "
                    f"Loss: {loss.item():.4f}"
                )

        # 计算平均指标
        avg_loss = total_loss / total_samples
        accuracy = total_correct / total_samples

        return avg_loss, accuracy

    def validate(
        self,
        val_loader: DataLoader,
        criterion: nn.Module,
    ) -> Dict[str, float]:
        """
        验证模型

        Args:
            val_loader: 验证数据加载器
            criterion: 损失函数

        Returns:
            包含验证指标的字典
        """
        self.model.eval()

        total_loss = 0.0
        all_predictions = []
        all_labels = []

        with torch.no_grad():
            for inputs, labels in val_loader:
                # 将数据移到设备
                inputs = inputs.to(self.device)
                labels = labels.to(self.device)

                # 前向传播
                outputs = self.model(inputs)

                # 计算损失
                loss = criterion(outputs, labels)
                total_loss += loss.item() * inputs.size(0)

                # 获取预测
                _, predicted = torch.max(outputs.data, 1)
                all_predictions.extend(predicted.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())

        # 转换为数组
        all_predictions = np.array(all_predictions)
        all_labels = np.array(all_labels)

        # 计算指标
        avg_loss = total_loss / len(all_labels)
        metrics = EvaluationMetrics.compute_all_metrics(all_predictions, all_labels)

        return {
            "loss": avg_loss,
            "accuracy": metrics["accuracy"],
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1_score": metrics["f1_score"],
        }

    def train(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader,
        num_epochs: int = 50,
        learning_rate: float = 0.001,
        weight_decay: float = 1e-5,
        save_best_model: bool = True,
    ) -> Dict[str, List]:
        """
        训练模型

        Args:
            train_loader: 训练数据加载器
            val_loader: 验证数据加载器
            num_epochs: 训练轮数
            learning_rate: 学习率
            weight_decay: 权重衰减
            save_best_model: 是否保存最佳模型

        Returns:
            训练历史记录
        """
        # 创建优化器
        optimizer = optim.Adam(
            self.model.parameters(),
            lr=learning_rate,
            weight_decay=weight_decay,
        )

        # 创建损失函数
        criterion = nn.CrossEntropyLoss()

        # 学习率调度器
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer,
            mode="min",
            factor=0.5,
            patience=5,
            verbose=True,
        )

        best_val_loss = float("inf")
        best_model_path = None
        train_start_time = time.time()

        logger.info(f"开始训练: {num_epochs} 个 epoch")

        for epoch in range(num_epochs):
            logger.info(f"\n=== Epoch [{epoch + 1}/{num_epochs}] ===")

            # 训练
            train_loss, train_accuracy = self.train_epoch(
                train_loader, optimizer, criterion
            )

            logger.info(
                f"训练 - Loss: {train_loss:.4f}, Accuracy: {train_accuracy:.4f}"
            )

            # 验证
            val_metrics = self.validate(val_loader, criterion)

            logger.info(
                f"验证 - Loss: {val_metrics['loss']:.4f}, "
                f"Accuracy: {val_metrics['accuracy']:.4f}, "
                f"Precision: {val_metrics['precision']:.4f}, "
                f"Recall: {val_metrics['recall']:.4f}, "
                f"F1: {val_metrics['f1_score']:.4f}"
            )

            # 记录历史
            self.training_history["train_loss"].append(train_loss)
            self.training_history["train_accuracy"].append(train_accuracy)
            self.training_history["val_loss"].append(val_metrics["loss"])
            self.training_history["val_accuracy"].append(val_metrics["accuracy"])
            self.training_history["val_precision"].append(val_metrics["precision"])
            self.training_history["val_recall"].append(val_metrics["recall"])
            self.training_history["val_f1"].append(val_metrics["f1_score"])

            # 学习率调度
            scheduler.step(val_metrics["loss"])

            # 保存最佳模型
            if save_best_model and val_metrics["loss"] < best_val_loss:
                best_val_loss = val_metrics["loss"]
                best_model_path = self._save_model(
                    f"best_model_epoch_{epoch + 1}.pth"
                )
                logger.info(f"保存最佳模型: {best_model_path}")

        total_train_time = time.time() - train_start_time
        logger.info(f"训练完成, 总耗时: {total_train_time:.1f}s")

        return self.training_history

    def _save_model(self, filename: str) -> Path:
        """
        保存模型

        Args:
            filename: 文件名

        Returns:
            保存的模型路径
        """
        model_path = self.model_save_dir / filename
        torch.save(self.model.state_dict(), model_path)
        return model_path

    def load_model(self, model_path: str) -> bool:
        """
        加载模型

        Args:
            model_path: 模型文件路径

        Returns:
            加载是否成功
        """
        try:
            model_path = Path(model_path)

            # 第一步：验证模型文件
            valid, error_msg = TrainingService._validate_model_file(str(model_path))
            if not valid:
                logger.error(f"[MODEL_FILE_VALIDATION_FAILED] filePath={model_path}, error={error_msg}")
                return False

            logger.info(f"[MODEL_FILE_VALIDATION_PASS] filePath={model_path}")

            # 第二步：尝试加载模型
            try:
                state_dict = torch.load(model_path, map_location=self.device)
                logger.info(f"[MODEL_LOADED] filePath={model_path}")
            except Exception as load_error:
                error_msg = f"模型文件损坏或格式错误: {str(load_error)}"
                logger.error(f"[MODEL_LOAD_ERROR] filePath={model_path}, error={error_msg}")
                return False

            # 第三步：验证 state_dict
            if not isinstance(state_dict, dict):
                error_msg = "模型状态字典格式错误"
                logger.error(f"[MODEL_STATE_DICT_INVALID] filePath={model_path}")
                return False

            if not state_dict:
                error_msg = "模型状态字典为空"
                logger.error(f"[MODEL_STATE_DICT_EMPTY] filePath={model_path}")
                return False

            # 第四步：加载到模型
            try:
                self.model.load_state_dict(state_dict)
                logger.info(f"[MODEL_LOAD_SUCCESS] filePath={model_path}")
                return True
            except Exception as load_error:
                error_msg = f"模型权重加载失败: {str(load_error)}"
                logger.error(f"[MODEL_WEIGHT_LOAD_ERROR] filePath={model_path}, error={error_msg}")
                return False

        except Exception as e:
            logger.error(f"[MODEL_LOAD_EXCEPTION] filePath={model_path}, error={str(e)}")
            return False

    def save_training_history(self, history_path: str) -> bool:
        """
        保存训练历史

        Args:
            history_path: 历史文件路径

        Returns:
            保存是否成功
        """
        try:
            history_path = Path(history_path)
            history_path.parent.mkdir(parents=True, exist_ok=True)

            with open(history_path, "w") as f:
                json.dump(self.training_history, f, indent=2)

            logger.info(f"训练历史已保存: {history_path}")
            return True

        except Exception as e:
            logger.error(f"保存训练历史失败: {str(e)}")
            return False

    def get_training_summary(self) -> Dict:
        """
        获取训练总结

        Returns:
            训练总结字典
        """
        if not self.training_history["train_loss"]:
            return {}

        return {
            "total_epochs": len(self.training_history["train_loss"]),
            "best_train_loss": min(self.training_history["train_loss"]),
            "best_train_accuracy": max(self.training_history["train_accuracy"]),
            "best_val_loss": min(self.training_history["val_loss"]),
            "best_val_accuracy": max(self.training_history["val_accuracy"]),
            "best_val_f1": max(self.training_history["val_f1"]),
            "final_train_loss": self.training_history["train_loss"][-1],
            "final_train_accuracy": self.training_history["train_accuracy"][-1],
            "final_val_loss": self.training_history["val_loss"][-1],
            "final_val_accuracy": self.training_history["val_accuracy"][-1],
            "final_val_f1": self.training_history["val_f1"][-1],
        }
