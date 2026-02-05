"""
后台任务管理模块
用于管理异步后台任务的生命周期和状态
"""

import uuid
import logging
import threading
import shutil
import json
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum
from pathlib import Path

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

    def submit_merge_task(
        self,
        uploadId: str,
        fileName: str,
        fileSize: int,
        totalChunks: int,
    ) -> str:
        """
        提交文件合并任务

        Args:
            uploadId: 上传会话 ID
            fileName: 文件名
            fileSize: 文件大小
            totalChunks: 总分片数

        Returns:
            任务 ID
        """
        task_id = self.create_task(task_type="file_merge")
        self.start_task(task_id)

        # 在后台线程中执行合并
        merge_thread = threading.Thread(
            target=self._execute_merge_task,
            args=(task_id, uploadId, fileName, fileSize, totalChunks),
            daemon=True,
        )
        merge_thread.start()

        logger.info(f"[MERGE_THREAD_STARTED] taskId={task_id}, uploadId={uploadId}")

        return task_id

    def _execute_merge_task(
        self,
        task_id: str,
        uploadId: str,
        fileName: str,
        fileSize: int,
        totalChunks: int,
    ) -> None:
        """
        执行文件合并任务（在后台线程中运行）

        Args:
            task_id: 任务 ID
            uploadId: 上传会话 ID
            fileName: 文件名
            fileSize: 文件大小
            totalChunks: 总分片数
        """
        try:
            from backend.config.settings import TEMP_DIR, DETECTION_IMAGES_DIR
            from backend.models.database import UploadSession, get_db_manager

            logger.info(f"[MERGE_EXECUTING] taskId={task_id}, uploadId={uploadId}")

            # 更新任务进度
            self.update_progress(task_id, 10, "准备合并文件")

            # 合并分片
            session_dir = Path(TEMP_DIR) / uploadId
            output_dir = Path(DETECTION_IMAGES_DIR)
            output_dir.mkdir(parents=True, exist_ok=True)

            output_path = output_dir / fileName

            logger.info(f"[MERGE_COMBINING] uploadId={uploadId}, outputPath={output_path}")

            with open(output_path, "wb") as output_file:
                for i in range(totalChunks):
                    chunk_path = session_dir / f"chunk_{i}"
                    if not chunk_path.exists():
                        raise FileNotFoundError(f"分片文件丢失: chunk_{i}")

                    with open(chunk_path, "rb") as chunk_file:
                        output_file.write(chunk_file.read())

                    # 更新进度
                    progress = 10 + int((i / totalChunks) * 80)
                    self.update_progress(task_id, progress, f"合并中 ({i+1}/{totalChunks})")

            # 验证文件大小
            actual_size = output_path.stat().st_size
            if actual_size != fileSize:
                output_path.unlink()
                raise ValueError(
                    f"文件大小不匹配: 期望 {fileSize}, 实际 {actual_size}"
                )

            logger.info(
                f"[MERGE_COMPLETE] uploadId={uploadId}, filePath={output_path}, "
                f"fileSize={actual_size}"
            )

            # 更新数据库中的会话状态
            db_manager = get_db_manager()
            db_session = db_manager.get_session()
            try:
                upload_session = db_session.query(UploadSession).filter(
                    UploadSession.upload_id == uploadId
                ).first()

                if upload_session:
                    upload_session.status = "completed"
                    upload_session.file_path = str(output_path)
                    upload_session.updated_at = datetime.now()
                    db_session.commit()
                    logger.info(f"[SESSION_UPDATED] uploadId={uploadId}, status=completed")
                else:
                    logger.warning(f"[SESSION_NOT_FOUND] uploadId={uploadId}")

            finally:
                db_session.close()

            # 清理临时文件
            shutil.rmtree(session_dir, ignore_errors=True)
            logger.info(f"[TEMP_CLEANED] uploadId={uploadId}")

            # 标记任务完成
            self.complete_task(
                task_id,
                result={
                    "uploadId": uploadId,
                    "filePath": str(output_path),
                    "fileName": fileName,
                    "fileSize": actual_size,
                },
            )

            logger.info(f"[MERGE_SUCCESS] taskId={task_id}, uploadId={uploadId}")

        except Exception as e:
            logger.error(f"[MERGE_FAILED] taskId={task_id}, uploadId={uploadId}, error={str(e)}")

            # 更新数据库中的会话状态为失败
            try:
                from backend.models.database import UploadSession, get_db_manager

                db_manager = get_db_manager()
                db_session = db_manager.get_session()
                try:
                    upload_session = db_session.query(UploadSession).filter(
                        UploadSession.upload_id == uploadId
                    ).first()

                    if upload_session:
                        upload_session.status = "failed"
                        upload_session.error_message = str(e)
                        upload_session.updated_at = datetime.now()
                        db_session.commit()
                        logger.info(f"[SESSION_FAILED] uploadId={uploadId}")

                finally:
                    db_session.close()

            except Exception as db_error:
                logger.error(f"[SESSION_UPDATE_FAILED] uploadId={uploadId}, error={str(db_error)}")

            # 标记任务失败
            self.fail_task(task_id, str(e))


# 全局任务管理器实例
_task_manager = BackgroundTaskManager()


def get_task_manager() -> BackgroundTaskManager:
    """获取全局任务管理器实例"""
    return _task_manager
