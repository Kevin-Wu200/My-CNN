"""
任务管理服务模块
用于统一管理训练和检测任务的状态
"""

import json
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime

from backend.models.database import DatabaseManager, TrainingTask, DetectionTask

logger = logging.getLogger(__name__)


class TaskManagementService:
    """任务管理服务类"""

    def __init__(self, db_manager: DatabaseManager):
        """
        初始化任务管理服务

        Args:
            db_manager: 数据库管理器
        """
        self.db_manager = db_manager

    def get_training_task_status(self, task_id: int) -> Dict[str, Any]:
        """
        获取训练任务状态

        Args:
            task_id: 任务 ID

        Returns:
            任务状态字典
        """
        try:
            session = self.db_manager.get_session()

            task = session.query(TrainingTask).filter_by(id=task_id).first()
            if not task:
                session.close()
                return {
                    "success": False,
                    "error": f"任务不存在: {task_id}",
                }

            # 解析模型配置
            try:
                model_config = json.loads(task.model_config)
            except:
                model_config = {}

            # 解析训练历史
            try:
                training_history = json.loads(task.training_history) if task.training_history else {}
            except:
                training_history = {}

            result = {
                "success": True,
                "task_id": task.id,
                "user_id": task.user_id,
                "task_name": task.task_name,
                "status": task.status,
                "progress": task.progress,
                "model_config": model_config,
                "model_path": task.model_path,
                "training_history": training_history,
                "error_message": task.error_message,
                "created_at": task.created_at.isoformat(),
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            }

            session.close()

            return result

        except Exception as e:
            logger.error(f"获取训练任务状态失败: {str(e)}")
            return {
                "success": False,
                "error": f"获取任务状态失败: {str(e)}",
            }

    def get_detection_task_status(self, task_id: int) -> Dict[str, Any]:
        """
        获取检测任务状态

        Args:
            task_id: 任务 ID

        Returns:
            任务状态字典
        """
        try:
            session = self.db_manager.get_session()

            task = session.query(DetectionTask).filter_by(id=task_id).first()
            if not task:
                session.close()
                return {
                    "success": False,
                    "error": f"任务不存在: {task_id}",
                }

            # 解析检测结果
            try:
                detection_results = json.loads(task.detection_results) if task.detection_results else {}
            except:
                detection_results = {}

            # 解析变化检测结果
            try:
                change_detection_results = json.loads(task.change_detection_results) if task.change_detection_results else {}
            except:
                change_detection_results = {}

            result = {
                "success": True,
                "task_id": task.id,
                "user_id": task.user_id,
                "task_name": task.task_name,
                "status": task.status,
                "progress": task.progress,
                "model_id": task.model_id,
                "detection_results": detection_results,
                "change_detection_results": change_detection_results,
                "error_message": task.error_message,
                "created_at": task.created_at.isoformat(),
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            }

            session.close()

            return result

        except Exception as e:
            logger.error(f"获取检测任务状态失败: {str(e)}")
            return {
                "success": False,
                "error": f"获取任务状态失败: {str(e)}",
            }

    def update_training_task(
        self,
        task_id: int,
        status: str,
        progress: float = 0.0,
        model_path: Optional[str] = None,
        training_history: Optional[Dict] = None,
        error_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        更新训练任务

        Args:
            task_id: 任务 ID
            status: 任务状态
            progress: 进度（0-100）
            model_path: 模型路径
            training_history: 训练历史
            error_message: 错误信息

        Returns:
            更新结果字典
        """
        try:
            session = self.db_manager.get_session()

            task = session.query(TrainingTask).filter_by(id=task_id).first()
            if not task:
                session.close()
                return {
                    "success": False,
                    "error": f"任务不存在: {task_id}",
                }

            # 更新任务信息
            task.status = status
            task.progress = progress

            if model_path:
                task.model_path = model_path

            if training_history:
                task.training_history = json.dumps(training_history)

            if error_message:
                task.error_message = error_message

            if status == "running" and not task.started_at:
                task.started_at = datetime.now()
            elif status == "completed":
                task.completed_at = datetime.now()

            session.commit()
            session.close()

            logger.info(f"训练任务已更新: {task_id} -> {status}")

            return {
                "success": True,
                "message": "训练任务更新成功",
                "task_id": task_id,
            }

        except Exception as e:
            logger.error(f"更新训练任务失败: {str(e)}")
            return {
                "success": False,
                "error": f"更新训练任务失败: {str(e)}",
            }

    def update_detection_task(
        self,
        task_id: int,
        status: str,
        progress: float = 0.0,
        detection_results: Optional[Dict] = None,
        change_detection_results: Optional[Dict] = None,
        error_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        更新检测任务

        Args:
            task_id: 任务 ID
            status: 任务状态
            progress: 进度（0-100）
            detection_results: 检测结果
            change_detection_results: 变化检测结果
            error_message: 错误信息

        Returns:
            更新结果字典
        """
        try:
            session = self.db_manager.get_session()

            task = session.query(DetectionTask).filter_by(id=task_id).first()
            if not task:
                session.close()
                return {
                    "success": False,
                    "error": f"任务不存在: {task_id}",
                }

            # 更新任务信息
            task.status = status
            task.progress = progress

            if detection_results:
                task.detection_results = json.dumps(detection_results)

            if change_detection_results:
                task.change_detection_results = json.dumps(change_detection_results)

            if error_message:
                task.error_message = error_message

            if status == "running" and not task.started_at:
                task.started_at = datetime.now()
            elif status == "completed":
                task.completed_at = datetime.now()

            session.commit()
            session.close()

            logger.info(f"检测任务已更新: {task_id} -> {status}")

            return {
                "success": True,
                "message": "检测任务更新成功",
                "task_id": task_id,
            }

        except Exception as e:
            logger.error(f"更新检测任务失败: {str(e)}")
            return {
                "success": False,
                "error": f"更新检测任务失败: {str(e)}",
            }

    def get_model_config_options() -> Dict[str, Any]:
        """
        获取模型配置选项

        Returns:
            模型配置选项字典
        """
        return {
            "backbone_types": [
                {"value": "vgg", "label": "VGG"},
                {"value": "resnet", "label": "ResNet"},
                {"value": "densenet", "label": "DenseNet"},
                {"value": "mobilenet", "label": "MobileNet"},
                {"value": "efficientnet", "label": "EfficientNet"},
            ],
            "temporal_module_types": [
                {"value": "lstm", "label": "LSTM"},
                {"value": "gru", "label": "GRU"},
                {"value": "temporal_conv", "label": "Temporal Convolution"},
                {"value": "conv3d", "label": "3D Convolution"},
            ],
            "kernel_sizes": [
                {"value": 3, "label": "3x3"},
                {"value": 5, "label": "5x5"},
                {"value": 7, "label": "7x7"},
            ],
            "num_filters": [
                {"value": 32, "label": "32"},
                {"value": 64, "label": "64"},
                {"value": 128, "label": "128"},
                {"value": 256, "label": "256"},
            ],
            "activation_functions": [
                {"value": "relu", "label": "ReLU"},
                {"value": "elu", "label": "ELU"},
                {"value": "gelu", "label": "GELU"},
            ],
            "num_classes": [
                {"value": 2, "label": "Binary Classification (2 classes)"},
                {"value": 3, "label": "Multi-class (3 classes)"},
            ],
        }
