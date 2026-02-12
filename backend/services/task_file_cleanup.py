"""
任务文件清理服务

在无监督检测任务完成后，自动清理与该任务相关的文件：
- storage/merged/{uploadId}.tif (合并后的原始文件，唯一数据源)

优化说明：
- 移除了文件复制逻辑，使用 merged 文件作为唯一数据源
- 避免重复存储，节省磁盘空间

严格限制：
1. 不影响现有上传、检测和任务查询逻辑
2. 不删除检测结果文件（结果存储在数据库中）
3. 不删除仍在使用中的文件
4. 不在任务运行期间删除文件
5. 如果无法确保安全删除，则放弃删除
6. 清理动作延迟 120 秒执行，防止异步读写冲突
"""

import logging
import time
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from backend.utils.file_path_manager import FilePathManager
from backend.models.database import get_db_manager, UploadSession

logger = logging.getLogger(__name__)


class TaskFileCleanupService:
    """任务文件清理服务"""

    # 允许删除的目录列表（白名单机制）
    _ALLOWED_CLEANUP_DIRS = [
        "storage/merged",
        "storage/detection_images",
    ]

    # 禁止删除的目录列表（黑名单机制）
    _FORBIDDEN_CLEANUP_DIRS = [
        "storage/models",
        "storage/training_samples",
        "storage/uploads",
    ]

    @classmethod
    def _validate_file_path_for_cleanup(cls, file_path: Path) -> bool:
        """
        验证文件路径是否可以安全删除

        Args:
            file_path: 文件路径

        Returns:
            是否可以安全删除
        """
        try:
            # 第一步：验证文件路径在存储目录内
            if not FilePathManager.validate_path_is_in_storage(str(file_path)):
                logger.warning(f"[CLEANUP_VALIDATION_FAILED] 文件路径不在存储目录内: {file_path}")
                return False

            # 第二步：验证文件真实存在
            if not file_path.exists():
                logger.info(f"[CLEANUP_SKIP] 文件不存在，跳过删除: {file_path}")
                return False

            # 第三步：验证文件路径属于允许删除的目录
            file_path_str = str(file_path.resolve())
            storage_root = FilePathManager.get_storage_root().resolve()

            # 检查是否在允许的目录中
            is_in_allowed_dir = False
            for allowed_dir in cls._ALLOWED_CLEANUP_DIRS:
                allowed_path = (storage_root / allowed_dir).resolve()
                try:
                    file_path.resolve().relative_to(allowed_path)
                    is_in_allowed_dir = True
                    break
                except ValueError:
                    continue

            if not is_in_allowed_dir:
                logger.warning(f"[CLEANUP_VALIDATION_FAILED] 文件路径不在允许删除的目录中: {file_path}")
                return False

            # 第四步：验证文件路径不属于禁止删除的目录
            for forbidden_dir in cls._FORBIDDEN_CLEANUP_DIRS:
                forbidden_path = (storage_root / forbidden_dir).resolve()
                try:
                    file_path.resolve().relative_to(forbidden_path)
                    logger.error(f"[CLEANUP_VALIDATION_FAILED] 文件路径在禁止删除的目录中: {file_path}")
                    return False
                except ValueError:
                    continue

            logger.info(f"[CLEANUP_VALIDATION_PASS] 文件路径验证通过: {file_path}")
            return True

        except Exception as e:
            logger.error(f"[CLEANUP_VALIDATION_ERROR] 验证文件路径时发生错误: {file_path}, error={str(e)}")
            return False

    @classmethod
    def _safe_delete_file(cls, file_path: Path) -> bool:
        """
        安全删除单个文件

        Args:
            file_path: 文件路径

        Returns:
            是否删除成功
        """
        try:
            # 验证文件路径
            if not cls._validate_file_path_for_cleanup(file_path):
                logger.warning(f"[CLEANUP_SKIP] 文件路径验证失败，跳过删除: {file_path}")
                return False

            # 删除文件
            file_path.unlink()
            logger.info(f"[FILE_DELETED] 文件已删除: {file_path}")
            return True

        except FileNotFoundError:
            logger.info(f"[CLEANUP_SKIP] 文件不存在，跳过删除: {file_path}")
            return False
        except PermissionError as e:
            logger.error(f"[CLEANUP_FAILED] 权限不足，无法删除文件: {file_path}, error={str(e)}")
            return False
        except Exception as e:
            logger.error(f"[CLEANUP_FAILED] 删除文件时发生错误: {file_path}, error={str(e)}")
            return False

    @classmethod
    def _find_related_files(cls, task_result: Dict[str, Any]) -> List[Path]:
        """
        根据任务结果查找相关文件

        优化后的逻辑：由于移除了文件复制，image_path 直接指向 merged 文件（唯一数据源）

        Args:
            task_result: 任务结果数据

        Returns:
            相关文件路径列表
        """
        related_files = []

        try:
            # 从任务结果中获取 image_path
            image_path = task_result.get("image_path")
            if not image_path:
                logger.warning("[CLEANUP_SKIP] 任务结果中没有 image_path")
                return related_files

            # 优化：image_path 现在直接指向 merged 文件（唯一数据源）
            # 不再需要查询数据库或查找其他文件
            merged_file = Path(image_path)
            if merged_file.exists():
                related_files.append(merged_file)
                logger.info(f"[CLEANUP_FILE_FOUND] 合并文件（唯一数据源）: {merged_file}")
            else:
                logger.warning(f"[CLEANUP_SKIP] 文件不存在: {merged_file}")

        except Exception as e:
            logger.error(f"[CLEANUP_ERROR] 查找相关文件时发生错误: {str(e)}")

        return related_files

    @classmethod
    def _cleanup_task_files(cls, task_id: str, task_result: Dict[str, Any]) -> None:
        """
        清理任务相关文件（内部方法，由延迟线程调用）

        Args:
            task_id: 任务ID
            task_result: 任务结果数据
        """
        logger.info(f"[CLEANUP_START] 开始清理任务文件: task_id={task_id}")

        try:
            # 查找相关文件
            related_files = cls._find_related_files(task_result)

            if not related_files:
                logger.info(f"[CLEANUP_SKIP] 没有找到需要清理的文件: task_id={task_id}")
                return

            # 优化：现在只有 merged 文件（唯一数据源），无需排序
            deleted_count = 0
            failed_count = 0

            for file_path in related_files:
                logger.info(f"[CLEANUP_DELETING] 正在删除文件: {file_path}")
                if cls._safe_delete_file(file_path):
                    deleted_count += 1
                else:
                    failed_count += 1

            logger.info(
                f"[CLEANUP_COMPLETE] 任务文件清理完成: task_id={task_id}, "
                f"deleted={deleted_count}, failed={failed_count}"
            )

        except Exception as e:
            logger.error(f"[CLEANUP_ERROR] 清理任务文件时发生错误: task_id={task_id}, error={str(e)}")

    @classmethod
    def schedule_cleanup(cls, task_id: str, task_result: Dict[str, Any], delay_seconds: int = 120) -> None:
        """
        调度任务文件清理（延迟执行）

        Args:
            task_id: 任务ID
            task_result: 任务结果数据
            delay_seconds: 延迟秒数（默认120秒）
        """
        def delayed_cleanup():
            try:
                logger.info(
                    f"[CLEANUP_SCHEDULED] 任务文件清理已调度: task_id={task_id}, "
                    f"delay={delay_seconds}s, scheduled_at={datetime.now().isoformat()}"
                )
                time.sleep(delay_seconds)
                logger.info(f"[CLEANUP_EXECUTING] 开始执行延迟清理: task_id={task_id}")
                cls._cleanup_task_files(task_id, task_result)
            except Exception as e:
                logger.error(f"[CLEANUP_THREAD_ERROR] 清理线程发生错误: task_id={task_id}, error={str(e)}")

        # 启动后台线程执行延迟清理
        cleanup_thread = threading.Thread(
            target=delayed_cleanup,
            name=f"cleanup-{task_id}",
            daemon=True
        )
        cleanup_thread.start()
        logger.info(f"[CLEANUP_THREAD_STARTED] 清理线程已启动: task_id={task_id}, thread={cleanup_thread.name}")
