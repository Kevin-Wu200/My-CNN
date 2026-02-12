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

from backend.models.task_storage import TaskStorage

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BackgroundTaskManager:
    """后台任务管理器"""

    def __init__(self):
        """初始化任务管理器"""
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.progress_timestamps: Dict[str, float] = {}  # 记录进度最后更新时间
        self.active_threads: Dict[str, threading.Thread] = {}  # 跟踪活动线程
        self.active_processes: Dict[str, Any] = {}  # 跟踪活动进程（multiprocessing.Process或Pool）
        self.task_stop_flags: Dict[str, threading.Event] = {}  # 任务停止标志
        self._shutdown_flag = threading.Event()  # 关闭协调标志
        # 初始化持久化存储
        self.storage = TaskStorage()

        # 从存储加载任务
        self._load_tasks_from_storage()

    def _load_tasks_from_storage(self) -> None:
        """从持久化存储加载任务"""
        try:
            stored_tasks = self.storage.load_all_tasks()
            self.tasks.update(stored_tasks)
            logger.info(f"从存储加载了 {len(stored_tasks)} 个任务")

            # 将运行中的任务标记为失败（进程重启导致）
            for task_id, task in self.tasks.items():
                if task["status"] == TaskStatus.RUNNING:
                    logger.warning(f"任务 {task_id} 在重启前处于运行状态，标记为失败")
                    self.fail_task(task_id, "服务器重启，任务被中断")
        except Exception as e:
            logger.error(f"加载任务失败: {str(e)}")

    def create_task(self, task_type: str, user_id: Optional[str] = None, task_id: Optional[str] = None) -> str:
        """
        创建新任务

        Args:
            task_type: 任务类型（unsupervised_detection, detection, training等）
            user_id: 用户ID（可选）
            task_id: 任务ID（可选，如果不提供则自动生成）

        Returns:
            任务ID
        """
        if task_id is None:
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
        # 持久化任务
        self.storage.save_task(task)
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
        # 持久化任务
        self.storage.save_task(self.tasks[task_id])
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
        # 持久化任务
        self.storage.save_task(self.tasks[task_id])
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
        # 持久化任务
        self.storage.save_task(self.tasks[task_id])
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
        # 持久化任务
        self.storage.save_task(self.tasks[task_id])
        return True

    def cancel_task(self, task_id: str, reason: str = "用户取消") -> bool:
        """
        标记任务为已取消

        Args:
            task_id: 任务ID
            reason: 取消原因

        Returns:
            是否成功
        """
        if task_id not in self.tasks:
            logger.warning(f"任务不存在: {task_id}")
            return False

        self.tasks[task_id]["status"] = TaskStatus.CANCELLED
        self.tasks[task_id]["completed_at"] = datetime.now().isoformat()
        self.tasks[task_id]["error"] = reason
        logger.info(f"任务已取消: {task_id} - {reason}")
        # 持久化任务
        self.storage.save_task(self.tasks[task_id])
        return True

    def register_thread(self, task_id: str, thread: threading.Thread) -> None:
        """
        注册任务的线程句柄

        Args:
            task_id: 任务ID
            thread: 线程对象
        """
        self.active_threads[task_id] = thread
        logger.info(f"[THREAD_REGISTERED] taskId={task_id}, threadName={thread.name}")

    def register_process(self, task_id: str, process: Any) -> None:
        """
        注册任务的进程句柄

        Args:
            task_id: 任务ID
            process: 进程对象（multiprocessing.Process或Pool）
        """
        self.active_processes[task_id] = process
        logger.info(f"[PROCESS_REGISTERED] taskId={task_id}, processType={type(process).__name__}")

    def get_stop_flag(self, task_id: str) -> threading.Event:
        """
        获取任务的停止标志

        Args:
            task_id: 任务ID

        Returns:
            停止标志事件对象
        """
        if task_id not in self.task_stop_flags:
            self.task_stop_flags[task_id] = threading.Event()
        return self.task_stop_flags[task_id]

    def set_stop_flag(self, task_id: str) -> None:
        """
        设置任务的停止标志

        Args:
            task_id: 任务ID
        """
        stop_flag = self.get_stop_flag(task_id)
        stop_flag.set()
        logger.info(f"[STOP_FLAG_SET] taskId={task_id}")

    def is_stop_requested(self, task_id: str) -> bool:
        """
        检查是否请求停止任务

        Args:
            task_id: 任务ID

        Returns:
            是否请求停止
        """
        stop_flag = self.get_stop_flag(task_id)
        return stop_flag.is_set()

    def force_terminate_task(self, task_id: str) -> bool:
        """
        强制终止任务（包括线程和进程）

        Args:
            task_id: 任务ID

        Returns:
            是否成功
        """
        logger.info(f"[FORCE_TERMINATE_START] taskId={task_id}")

        # 第一步：设置停止标志
        self.set_stop_flag(task_id)

        # 第二步：终止线程
        if task_id in self.active_threads:
            thread = self.active_threads[task_id]
            if thread.is_alive():
                logger.warning(f"[THREAD_FORCE_TERMINATE] taskId={task_id}, threadName={thread.name}")
                # 等待线程自然退出（通过stop_flag）
                thread.join(timeout=5)
                if thread.is_alive():
                    logger.warning(f"[THREAD_STILL_ALIVE] taskId={task_id}, threadName={thread.name}")
            del self.active_threads[task_id]

        # 第三步：终止进程
        if task_id in self.active_processes:
            process = self.active_processes[task_id]
            process_type = type(process).__name__

            try:
                if process_type == "Pool":
                    # multiprocessing.Pool
                    logger.warning(f"[POOL_FORCE_TERMINATE] taskId={task_id}")
                    process.terminate()
                    process.join(timeout=5)
                elif hasattr(process, "terminate"):
                    # multiprocessing.Process
                    logger.warning(f"[PROCESS_FORCE_TERMINATE] taskId={task_id}")
                    process.terminate()
                    process.join(timeout=5)
                    if process.is_alive():
                        logger.error(f"[PROCESS_KILL] taskId={task_id}")
                        process.kill()
                        process.join(timeout=2)
            except Exception as e:
                logger.error(f"[PROCESS_TERMINATE_ERROR] taskId={task_id}, error={str(e)}")

            del self.active_processes[task_id]

        # 第四步：标记任务为已取消
        if task_id in self.tasks:
            self.cancel_task(task_id, "任务被强制终止")

        logger.info(f"[FORCE_TERMINATE_COMPLETE] taskId={task_id}")
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
            if task["status"] in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
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
            target=self._execute_merge_task_wrapper,
            args=(task_id, uploadId, fileName, fileSize, totalChunks),
            daemon=False,
            name=f"MergeThread-{task_id}"
        )
        self.active_threads[task_id] = merge_thread
        merge_thread.start()

        logger.info(f"[MERGE_THREAD_STARTED] taskId={task_id}, uploadId={uploadId}")

        return task_id

    def _execute_merge_task_wrapper(
        self,
        task_id: str,
        uploadId: str,
        fileName: str,
        fileSize: int,
        totalChunks: int,
    ) -> None:
        """
        包装器：执行合并任务并清理线程跟踪

        Args:
            task_id: 任务 ID
            uploadId: 上传会话 ID
            fileName: 文件名
            fileSize: 文件大小
            totalChunks: 总分片数
        """
        try:
            self._execute_merge_task(task_id, uploadId, fileName, fileSize, totalChunks)
        finally:
            # 清理线程跟踪
            if task_id in self.active_threads:
                del self.active_threads[task_id]
            logger.info(f"[THREAD_CLEANUP] taskId={task_id}")

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

        按照8个步骤修复分片合并流程：
        1. 定位并检查分片合并函数是否真的被调用，在合并函数入口和出口强制打印日志
        2. 确保合并逻辑只做一件事 - 按chunkIndex顺序读取所有分片文件，按二进制顺序写入一个新的完整tif文件
        3. 在合并前增加严格校验 - 校验分片数量是否大于1，校验每一个分片文件真实存在
        4. 合并成功后，明确生成一个唯一的完整tif文件路径，例如storage/merged/{uploadId}.tif，并立即校验该文件在磁盘上真实存在
        5. 将合并后的完整tif文件路径保存到后端的任务状态或上传记录中
        6. 禁止任何检测逻辑直接使用分片文件，检测模块只能接受"合并完成后的完整tif"
        7. 在无监督检测启动前，强制校验完整tif文件是否存在
        8. 在日志中明确区分三种状态 - 仅分片存在、合并进行中、合并完成且文件存在

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
            from backend.utils.file_path_manager import FilePathManager

            # 第1步：定位并检查分片合并函数是否真的被调用，在合并函数入口强制打印日志
            logger.info(f"[MERGE_EXECUTING_START] taskId={task_id}, uploadId={uploadId}, fileName={fileName}, totalChunks={totalChunks}")

            # 更新任务进度
            self.update_progress(task_id, 5, "准备合并文件")

            # 获取分片目录
            session_dir = FilePathManager.get_chunk_dir(uploadId)

            # 第8步：在日志中明确区分三种状态 - 仅分片存在
            logger.info(f"[CHUNK_STATUS_ONLY_CHUNKS_EXIST] uploadId={uploadId}, chunkDir={session_dir}, totalChunks={totalChunks}")

            # 第3步：在合并前增加严格校验 - 校验分片数量是否大于1
            if totalChunks <= 1:
                raise ValueError(f"分片数量无效: {totalChunks}，必须大于1")
            logger.info(f"[CHUNK_COUNT_VALIDATION_PASS] uploadId={uploadId}, totalChunks={totalChunks}")

            # 第3步：在合并前增加严格校验 - 校验每一个分片文件真实存在
            logger.info(f"[CHUNK_FILES_VALIDATION_START] uploadId={uploadId}")
            for i in range(totalChunks):
                chunk_path = FilePathManager.get_chunk_path(uploadId, i)
                if not chunk_path.exists():
                    raise FileNotFoundError(f"分片文件丢失: chunk_{i} at {chunk_path}")
                logger.debug(f"[CHUNK_FILE_EXISTS] uploadId={uploadId}, chunkIndex={i}, chunkPath={chunk_path}")
            logger.info(f"[CHUNK_FILES_VALIDATION_PASS] uploadId={uploadId}, allChunksExist=True")

            # 第4步：合并成功后，明确生成一个唯一的完整tif文件路径
            output_path = FilePathManager.get_merged_file_path(fileName, uploadId)
            logger.info(f"[MERGED_FILE_PATH_GENERATED] uploadId={uploadId}, outputPath={output_path}")

            # 第8步：在日志中明确区分三种状态 - 合并进行中
            logger.info(f"[MERGE_STATUS_MERGING_IN_PROGRESS] uploadId={uploadId}, outputPath={output_path}, totalChunks={totalChunks}")

            # 第2步：确保合并逻辑只做一件事 - 按chunkIndex顺序读取所有分片文件，按二进制顺序写入一个新的完整tif文件
            logger.info(f"[MERGE_COMBINING_START] uploadId={uploadId}, outputPath={output_path}, totalChunks={totalChunks}")

            with open(output_path, "wb") as output_file:
                for i in range(totalChunks):
                    chunk_path = FilePathManager.get_chunk_path(uploadId, i)
                    with open(chunk_path, "rb") as chunk_file:
                        chunk_data = chunk_file.read()
                        output_file.write(chunk_data)

                    # 更新进度
                    progress = 5 + int((i / totalChunks) * 75)
                    self.update_progress(task_id, progress, f"合并中 ({i+1}/{totalChunks})")
                    logger.debug(f"[CHUNK_MERGED] uploadId={uploadId}, chunkIndex={i}, chunkSize={len(chunk_data)}")

            # 验证文件大小
            actual_size = output_path.stat().st_size
            if actual_size != fileSize:
                output_path.unlink()
                raise ValueError(
                    f"文件大小不匹配: 期望 {fileSize}, 实际 {actual_size}"
                )
            logger.info(f"[FILE_SIZE_VALIDATION_PASS] uploadId={uploadId}, expectedSize={fileSize}, actualSize={actual_size}")

            logger.info(f"[MERGE_COMBINING_COMPLETE] uploadId={uploadId}, finalFilePath={output_path}, finalFileSize={actual_size}")

            # 第4步：合并成功后，立即校验该文件在磁盘上真实存在
            logger.info(f"[FILE_VALIDATION_START] uploadId={uploadId}, filePath={output_path}")

            # 检查文件是否存在
            if not output_path.exists():
                raise FileNotFoundError(f"合并后文件不存在: {output_path}")
            logger.info(f"[FILE_EXISTS_CHECK_PASS] uploadId={uploadId}, filePath={output_path}")

            # 检查文件大小是否大于 0
            if actual_size <= 0:
                output_path.unlink()
                raise ValueError(f"文件大小无效: {actual_size}")
            logger.info(f"[FILE_SIZE_CHECK_PASS] uploadId={uploadId}, size={actual_size}")

            # 检查文件是否可读
            try:
                with open(output_path, "rb") as test_file:
                    test_file.read(1)
                logger.info(f"[FILE_READABLE_CHECK_PASS] uploadId={uploadId}")
            except Exception as read_error:
                output_path.unlink()
                raise IOError(f"文件不可读: {str(read_error)}")

            logger.info(
                f"[FILE_VALIDATION_COMPLETE] uploadId={uploadId}, filePath={output_path}, "
                f"fileSize={actual_size}"
            )

            # 第8步：在日志中明确区分三种状态 - 合并完成且文件存在
            logger.info(f"[MERGE_STATUS_MERGE_COMPLETE_FILE_EXISTS] uploadId={uploadId}, filePath={output_path}, fileSize={actual_size}")

            # 优化：直接使用 merged 文件作为唯一数据源，不再复制到 detection_images
            # 这样可以避免重复存储，节省磁盘空间
            logger.info(f"[SINGLE_STORAGE_OPTIMIZATION] uploadId={uploadId}, 使用merged文件作为唯一数据源: {output_path}")

            # 第5步：将合并后的完整tif文件路径保存到后端的任务状态或上传记录中
            db_manager = get_db_manager()
            db_session = db_manager.get_session()
            try:
                upload_session = db_session.query(UploadSession).filter(
                    UploadSession.upload_id == uploadId
                ).first()

                if upload_session:
                    # 更新为 merge_complete
                    upload_session.status = "merge_complete"
                    upload_session.file_path = str(output_path)
                    upload_session.updated_at = datetime.now()
                    db_session.commit()
                    logger.info(
                        f"[MERGE_COMPLETE_STATUS_SET] uploadId={uploadId}, "
                        f"filePath={output_path}"
                    )
                    logger.info(f"[SINGLE_STORAGE_VERIFIED] uploadId={uploadId}, 文件仅存储在: {output_path}, 无重复副本")

                    # 更新为 completed
                    upload_session.status = "completed"
                    upload_session.updated_at = datetime.now()
                    db_session.commit()
                    logger.info(f"[FILE_READY_STATUS_SET] uploadId={uploadId}, 数据库路径={output_path}")
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

            # 第1步：在合并函数出口强制打印日志
            logger.info(f"[MERGE_EXECUTING_COMPLETE] taskId={task_id}, uploadId={uploadId}, filePath={output_path}")

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
                        logger.info(f"[SESSION_FAILED] uploadId={uploadId}, error={str(e)}")

                finally:
                    db_session.close()

            except Exception as db_error:
                logger.error(f"[SESSION_UPDATE_FAILED] uploadId={uploadId}, error={str(db_error)}")

            # 标记任务失败
            self.fail_task(task_id, str(e))

    def shutdown(self, timeout: int = 60) -> None:
        """
        关闭任务管理器，等待所有活动线程和进程完成

        Args:
            timeout: 等待超时时间（秒）
        """
        logger.info(f"[SHUTDOWN_START] activeThreads={len(self.active_threads)}, activeProcesses={len(self.active_processes)}")
        self._shutdown_flag.set()

        # 第一步：设置所有运行中任务的停止标志
        for task_id in list(self.task_stop_flags.keys()):
            task = self.tasks.get(task_id)
            if task and task["status"] == TaskStatus.RUNNING:
                logger.info(f"[SHUTDOWN_SET_STOP_FLAG] taskId={task_id}")
                self.set_stop_flag(task_id)

        # 第二步：等待所有线程完成
        remaining_timeout = timeout
        for task_id, thread in list(self.active_threads.items()):
            if thread.is_alive():
                logger.info(f"[SHUTDOWN_WAIT_THREAD] taskId={task_id}, threadName={thread.name}")
                thread.join(timeout=remaining_timeout)
                if thread.is_alive():
                    logger.warning(f"[SHUTDOWN_THREAD_TIMEOUT] taskId={task_id}, threadName={thread.name}")
                else:
                    logger.info(f"[SHUTDOWN_THREAD_COMPLETE] taskId={task_id}")
                remaining_timeout = max(5, remaining_timeout - 10)

        # 第三步：等待所有进程完成
        for task_id, process in list(self.active_processes.items()):
            process_type = type(process).__name__
            try:
                if process_type == "Pool":
                    logger.info(f"[SHUTDOWN_CLOSE_POOL] taskId={task_id}")
                    process.close()
                    process.join(timeout=remaining_timeout)
                elif hasattr(process, "is_alive") and process.is_alive():
                    logger.info(f"[SHUTDOWN_WAIT_PROCESS] taskId={task_id}")
                    process.join(timeout=remaining_timeout)
                    if process.is_alive():
                        logger.warning(f"[SHUTDOWN_PROCESS_TIMEOUT] taskId={task_id}")
                        process.terminate()
                        process.join(timeout=5)
                        if process.is_alive():
                            logger.error(f"[SHUTDOWN_PROCESS_KILL] taskId={task_id}")
                            process.kill()
            except Exception as e:
                logger.error(f"[SHUTDOWN_PROCESS_ERROR] taskId={task_id}, error={str(e)}")

        logger.info(f"[SHUTDOWN_COMPLETE] remainingThreads={len([t for t in self.active_threads.values() if t.is_alive()])}")


# 全局任务管理器实例
_task_manager = BackgroundTaskManager()


def get_task_manager() -> BackgroundTaskManager:
    """获取全局任务管理器实例"""
    return _task_manager
