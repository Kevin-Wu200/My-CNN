"""
后台任务管理模块
用于管理异步后台任务的生命周期和状态
"""

import uuid
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BackgroundTaskManager:
    """后台任务管理器"""

    def __init__(self):
        """初始化任务管理器"""
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.progress_timestamps: Dict[str, float] = {}  # 记录进度最后更新时间

    def create_task(self, task_type: str, user_id: Optional[str] = None) -> str:
        """
        创建新任务

        Args:
            task_type: 任务类型（unsupervised_detection, detection, training等）
            user_id: 用户ID（可选）

        Returns:
            任务ID
        """
        task_id = str(uuid.uuid4())
        task = {
            "task_id": task_id,
            "task_type": task_type,
            "user_id": user_id,
            "status": TaskStatus.PENDING,
            "progress": 0,
            "current_stage": "初始化",
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
        }
        self.tasks[task_id] = task
        logger.info(f"创建任务: {task_id} (类型: {task_type})")
        return task_id

    def start_task(self, task_id: str) -> bool:
        """
        标记任务为运行中

        Args:
            task_id: 任务ID

        Returns:
            是否成功
        """
        if task_id not in self.tasks:
            logger.warning(f"任务不存在: {task_id}")
            return False

        self.tasks[task_id]["status"] = TaskStatus.RUNNING
        self.tasks[task_id]["started_at"] = datetime.now().isoformat()
        logger.info(f"任务已启动: {task_id}")
        return True

    def update_progress(
        self, task_id: str, progress: int, stage: str = None
    ) -> bool:
        """
        更新任务进度

        Args:
            task_id: 任务ID
            progress: 进度百分比（0-100）
            stage: 当前阶段描述

        Returns:
            是否成功
        """
        if task_id not in self.tasks:
            logger.warning(f"任务不存在: {task_id}")
            return False

        self.tasks[task_id]["progress"] = min(100, max(0, progress))
        if stage:
            self.tasks[task_id]["current_stage"] = stage

        # 记录进度更新时间戳，用于检测进度是否卡住
        self.progress_timestamps[task_id] = datetime.now().timestamp()
        return True

    def complete_task(self, task_id: str, result: Any = None) -> bool:
        """
        标记任务为完成

        Args:
            task_id: 任务ID
            result: 任务结果

        Returns:
            是否成功
        """
        if task_id not in self.tasks:
            logger.warning(f"任务不存在: {task_id}")
            return False

        self.tasks[task_id]["status"] = TaskStatus.COMPLETED
        self.tasks[task_id]["progress"] = 100
        self.tasks[task_id]["completed_at"] = datetime.now().isoformat()
        self.tasks[task_id]["result"] = result
        logger.info(f"任务已完成: {task_id}")
        return True

    def fail_task(self, task_id: str, error: str) -> bool:
        """
        标记任务为失败

        Args:
            task_id: 任务ID
            error: 错误信息

        Returns:
            是否成功
        """
        if task_id not in self.tasks:
            logger.warning(f"任务不存在: {task_id}")
            return False

        self.tasks[task_id]["status"] = TaskStatus.FAILED
        self.tasks[task_id]["completed_at"] = datetime.now().isoformat()
        self.tasks[task_id]["error"] = error
        logger.error(f"任务失败: {task_id} - {error}")
        return True

    def get_task_status(self, task_id: str, stuck_threshold: int = 30) -> Optional[Dict[str, Any]]:
        """
        获取任务状态

        Args:
            task_id: 任务ID
            stuck_threshold: 进度停留超过多少秒判定为卡住（默认30秒）

        Returns:
            任务状态字典，如果任务不存在返回None
        """
        task = self.tasks.get(task_id)
        if not task:
            return None

        # 检测进度是否卡住
        if task["status"] == TaskStatus.RUNNING:
            last_update = self.progress_timestamps.get(task_id)
            if last_update:
                time_since_update = datetime.now().timestamp() - last_update
                if time_since_update > stuck_threshold:
                    task["stuck"] = True
                    task["stuck_duration"] = int(time_since_update)
                    logger.warning(
                        f"任务 {task_id} 进度卡住: "
                        f"进度={task['progress']}%, "
                        f"停留时间={time_since_update:.1f}秒"
                    )
                else:
                    task["stuck"] = False
                    task["stuck_duration"] = 0
            else:
                task["stuck"] = False
                task["stuck_duration"] = 0

        return task

    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有任务

        Returns:
            所有任务的字典
        """
        return self.tasks.copy()

    def get_tasks_by_status(self, status: TaskStatus) -> Dict[str, Dict[str, Any]]:
        """
        按状态获取任务

        Args:
            status: 任务状态

        Returns:
            符合条件的任务字典
        """
        return {
            task_id: task
            for task_id, task in self.tasks.items()
            if task["status"] == status
        }

    def get_tasks_by_user(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        """
        按用户获取任务

        Args:
            user_id: 用户ID

        Returns:
            该用户的所有任务字典
        """
        return {
            task_id: task
            for task_id, task in self.tasks.items()
            if task["user_id"] == user_id
        }

    def cleanup_old_tasks(self, max_age_hours: int = 24) -> int:
        """
        清理旧任务（已完成或失败超过指定时间）

        Args:
            max_age_hours: 最大保留时间（小时）

        Returns:
            清理的任务数量
        """
        from datetime import timedelta

        now = datetime.now()
        removed_count = 0
        tasks_to_remove = []

        for task_id, task in self.tasks.items():
            if task["status"] in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                completed_at = datetime.fromisoformat(task["completed_at"])
                if now - completed_at > timedelta(hours=max_age_hours):
                    tasks_to_remove.append(task_id)

        for task_id in tasks_to_remove:
            del self.tasks[task_id]
            removed_count += 1

        if removed_count > 0:
            logger.info(f"清理了 {removed_count} 个旧任务")

        return removed_count


# 全局任务管理器实例
_task_manager = BackgroundTaskManager()


def get_task_manager() -> BackgroundTaskManager:
    """获取全局任务管理器实例"""
    return _task_manager
