"""
用户管理服务模块
用于处理用户注册、登录和历史任务管理
"""

import json
from datetime import datetime
from typing import Tuple, Optional, List, Dict
import logging

from backend.models.database import (
    DatabaseManager,
    User,
    TrainingTask,
    DetectionTask,
    CorrectionTask,
)

logger = logging.getLogger(__name__)


class UserManagementService:
    """用户管理服务类"""

    def __init__(self, db_manager: DatabaseManager):
        """
        初始化用户管理服务

        Args:
            db_manager: 数据库管理器
        """
        self.db_manager = db_manager

    def validate_phone(self, phone: str) -> Tuple[bool, str]:
        """
        校验手机号格式

        Args:
            phone: 手机号

        Returns:
            (是否有效, 错误信息)
        """
        if not phone:
            return False, "手机号不能为空"

        if not phone.isdigit():
            return False, "手机号只能包含数字"

        if len(phone) != 11:
            return False, "手机号必须是11位"

        return True, ""

    def register_user(self, phone: str) -> Tuple[bool, Optional[int], str]:
        """
        注册新用户（使用手机号）

        Args:
            phone: 手机号（11位）

        Returns:
            (注册是否成功, 用户 ID, 错误信息或成功消息)
        """
        try:
            # 校验手机号格式
            is_valid, error_msg = self.validate_phone(phone)
            if not is_valid:
                return False, None, error_msg

            session = self.db_manager.get_session()

            # 检查手机号是否已存在
            existing_user = session.query(User).filter_by(phone=phone).first()
            if existing_user:
                session.close()
                return False, None, f"手机号已注册: {phone}"

            # 创建新用户
            new_user = User(phone=phone)
            session.add(new_user)
            session.commit()

            user_id = new_user.id
            session.close()

            logger.info(f"用户注册成功: {phone} (ID: {user_id})")

            return True, user_id, "用户注册成功"

        except Exception as e:
            logger.error(f"用户注册失败: {str(e)}")
            return False, None, f"用户注册失败: {str(e)}"

    def login_user(self, phone: str) -> Tuple[bool, Optional[int], str]:
        """
        用户登录（使用手机号，不存在则自动注册）

        Args:
            phone: 手机号（11位）

        Returns:
            (登录是否成功, 用户 ID, 错误信息或成功消息)
        """
        try:
            # 校验手机号格式
            is_valid, error_msg = self.validate_phone(phone)
            if not is_valid:
                return False, None, error_msg

            session = self.db_manager.get_session()

            # 查找用户
            user = session.query(User).filter_by(phone=phone).first()

            if not user:
                # 用户不存在，自动注册
                user = User(phone=phone)
                session.add(user)
                session.commit()
                logger.info(f"新用户自动注册: {phone} (ID: {user.id})")
            else:
                # 更新最后登录时间
                user.last_login = datetime.now()
                session.commit()

            user_id = user.id
            session.close()

            logger.info(f"用户登录成功: {phone} (ID: {user_id})")

            return True, user_id, "登录成功"

        except Exception as e:
            logger.error(f"用户登录失败: {str(e)}")
            return False, None, f"用户登录失败: {str(e)}"

    def get_user_info(self, user_id: int) -> Tuple[bool, Optional[Dict], str]:
        """
        获取用户信息

        Args:
            user_id: 用户 ID

        Returns:
            (获取是否成功, 用户信息字典, 错误信息或成功消息)
        """
        try:
            session = self.db_manager.get_session()

            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                session.close()
                return False, None, f"用户不存在: {user_id}"

            user_info = {
                "id": user.id,
                "phone": user.phone,
                "username": user.username,
                "created_at": user.created_at.isoformat(),
                "last_login": user.last_login.isoformat() if user.last_login else None,
            }

            session.close()

            return True, user_info, "用户信息获取成功"

        except Exception as e:
            logger.error(f"获取用户信息失败: {str(e)}")
            return False, None, f"获取用户信息失败: {str(e)}"

    def create_training_task(
        self,
        user_id: int,
        task_name: str,
        sample_path: str,
        model_config: Dict,
    ) -> Tuple[bool, Optional[int], str]:
        """
        创建训练任务

        Args:
            user_id: 用户 ID
            task_name: 任务名称
            sample_path: 样本路径
            model_config: 模型配置字典

        Returns:
            (创建是否成功, 任务 ID, 错误信息或成功消息)
        """
        try:
            session = self.db_manager.get_session()

            # 验证用户存在
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                session.close()
                return False, None, f"用户不存在: {user_id}"

            # 创建训练任务
            task = TrainingTask(
                user_id=user_id,
                task_name=task_name,
                sample_path=sample_path,
                model_config=json.dumps(model_config),
                status="pending",
            )

            session.add(task)
            session.commit()

            task_id = task.id
            session.close()

            logger.info(f"训练任务创建成功: {task_name} (ID: {task_id})")

            return True, task_id, "训练任务创建成功"

        except Exception as e:
            logger.error(f"训练任务创建失败: {str(e)}")
            return False, None, f"训练任务创建失败: {str(e)}"

    def get_training_history(self, user_id: int) -> Tuple[bool, Optional[List[Dict]], str]:
        """
        获取用户的训练历史

        Args:
            user_id: 用户 ID

        Returns:
            (获取是否成功, 训练任务列表, 错误信息或成功消息)
        """
        try:
            session = self.db_manager.get_session()

            # 查询用户的所有训练任务
            tasks = (
                session.query(TrainingTask)
                .filter_by(user_id=user_id)
                .order_by(TrainingTask.created_at.desc())
                .all()
            )

            task_list = []
            for task in tasks:
                task_info = {
                    "id": task.id,
                    "task_name": task.task_name,
                    "sample_path": task.sample_path,
                    "status": task.status,
                    "progress": task.progress,
                    "model_path": task.model_path,
                    "created_at": task.created_at.isoformat(),
                    "completed_at": task.completed_at.isoformat()
                    if task.completed_at
                    else None,
                }
                task_list.append(task_info)

            session.close()

            logger.info(f"获取用户训练历史: {user_id}, 共 {len(task_list)} 个任务")

            return True, task_list, "训练历史获取成功"

        except Exception as e:
            logger.error(f"获取训练历史失败: {str(e)}")
            return False, None, f"获取训练历史失败: {str(e)}"

    def create_detection_task(
        self,
        user_id: int,
        task_name: str,
        image_path: str,
        model_id: int,
    ) -> Tuple[bool, Optional[int], str]:
        """
        创建检测任务

        Args:
            user_id: 用户 ID
            task_name: 任务名称
            image_path: 影像路径
            model_id: 使用的模型 ID（训练任务 ID）

        Returns:
            (创建是否成功, 任务 ID, 错误信息或成功消息)
        """
        try:
            session = self.db_manager.get_session()

            # 验证用户存在
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                session.close()
                return False, None, f"用户不存在: {user_id}"

            # 验证模型存在
            model_task = session.query(TrainingTask).filter_by(id=model_id).first()
            if not model_task:
                session.close()
                return False, None, f"模型不存在: {model_id}"

            # 创建检测任务
            task = DetectionTask(
                user_id=user_id,
                task_name=task_name,
                image_path=image_path,
                model_id=model_id,
                status="pending",
            )

            session.add(task)
            session.commit()

            task_id = task.id
            session.close()

            logger.info(f"检测任务创建成功: {task_name} (ID: {task_id})")

            return True, task_id, "检测任务创建成功"

        except Exception as e:
            logger.error(f"检测任务创建失败: {str(e)}")
            return False, None, f"检测任务创建失败: {str(e)}"

    def get_detection_history(self, user_id: int) -> Tuple[bool, Optional[List[Dict]], str]:
        """
        获取用户的检测历史

        Args:
            user_id: 用户 ID

        Returns:
            (获取是否成功, 检测任务列表, 错误信息或成功消息)
        """
        try:
            session = self.db_manager.get_session()

            # 查询用户的所有检测任务
            tasks = (
                session.query(DetectionTask)
                .filter_by(user_id=user_id)
                .order_by(DetectionTask.created_at.desc())
                .all()
            )

            task_list = []
            for task in tasks:
                task_info = {
                    "id": task.id,
                    "task_name": task.task_name,
                    "image_path": task.image_path,
                    "model_id": task.model_id,
                    "status": task.status,
                    "progress": task.progress,
                    "created_at": task.created_at.isoformat(),
                    "completed_at": task.completed_at.isoformat()
                    if task.completed_at
                    else None,
                }
                task_list.append(task_info)

            session.close()

            logger.info(f"获取用户检测历史: {user_id}, 共 {len(task_list)} 个任务")

            return True, task_list, "检测历史获取成功"

        except Exception as e:
            logger.error(f"获取检测历史失败: {str(e)}")
            return False, None, f"获取检测历史失败: {str(e)}"

    def update_task_status(
        self,
        task_type: str,
        task_id: int,
        status: str,
        progress: float = 0.0,
        error_message: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        更新任务状态

        Args:
            task_type: 任务类型（training 或 detection）
            task_id: 任务 ID
            status: 新状态
            progress: 进度（0-100）
            error_message: 错误信息

        Returns:
            (更新是否成功, 错误信息或成功消息)
        """
        try:
            session = self.db_manager.get_session()

            if task_type == "training":
                task = session.query(TrainingTask).filter_by(id=task_id).first()
            elif task_type == "detection":
                task = session.query(DetectionTask).filter_by(id=task_id).first()
            else:
                return False, f"不支持的任务类型: {task_type}"

            if not task:
                session.close()
                return False, f"任务不存在: {task_id}"

            # 更新状态
            task.status = status
            task.progress = progress

            if status == "running" and not task.started_at:
                task.started_at = datetime.now()
            elif status == "completed":
                task.completed_at = datetime.now()

            if error_message:
                task.error_message = error_message

            session.commit()
            session.close()

            logger.info(f"任务状态已更新: {task_type} {task_id} -> {status}")

            return True, "任务状态更新成功"

        except Exception as e:
            logger.error(f"任务状态更新失败: {str(e)}")
            return False, f"任务状态更新失败: {str(e)}"
