"""
资源清理工具模块
用于清理临时文件和释放系统资源
"""

import shutil
import os
from pathlib import Path
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


class ResourceCleanup:
    """资源清理工具类"""

    @staticmethod
    def cleanup_temp_files(temp_dir: Path) -> Tuple[bool, str]:
        """
        清理临时文件

        Args:
            temp_dir: 临时目录路径

        Returns:
            (清理是否成功, 错误信息或成功消息)
        """
        try:
            temp_dir = Path(temp_dir)

            if not temp_dir.exists():
                return True, "临时目录不存在，无需清理"

            # 删除目录中的所有文件
            shutil.rmtree(temp_dir)

            logger.info(f"临时文件已清理: {temp_dir}")

            return True, "临时文件清理成功"

        except Exception as e:
            logger.error(f"清理临时文件失败: {str(e)}")
            return False, f"清理失败: {str(e)}"

    @staticmethod
    def cleanup_old_files(
        directory: Path,
        max_age_days: int = 30,
    ) -> Tuple[bool, int, str]:
        """
        清理旧文件

        Args:
            directory: 目录路径
            max_age_days: 文件最大保留天数

        Returns:
            (清理是否成功, 删除的文件数, 错误信息或成功消息)
        """
        try:
            from datetime import datetime, timedelta

            directory = Path(directory)

            if not directory.exists():
                return True, 0, "目录不存在"

            # 计算截止时间
            cutoff_time = datetime.now() - timedelta(days=max_age_days)
            cutoff_timestamp = cutoff_time.timestamp()

            deleted_count = 0

            # 遍历目录中的文件
            for file_path in directory.rglob("*"):
                if not file_path.is_file():
                    continue

                # 获取文件修改时间
                file_mtime = os.path.getmtime(file_path)

                # 如果文件太旧，删除它
                if file_mtime < cutoff_timestamp:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                    except Exception as e:
                        logger.warning(f"删除文件失败: {file_path}, 错误: {str(e)}")

            logger.info(f"已清理 {deleted_count} 个旧文件")

            return True, deleted_count, f"清理成功: 删除 {deleted_count} 个文件"

        except Exception as e:
            logger.error(f"清理旧文件失败: {str(e)}")
            return False, 0, f"清理失败: {str(e)}"

    @staticmethod
    def get_directory_size(directory: Path) -> int:
        """
        获取目录大小

        Args:
            directory: 目录路径

        Returns:
            目录大小（字节）
        """
        try:
            directory = Path(directory)

            if not directory.exists():
                return 0

            total_size = 0

            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size

            return total_size

        except Exception as e:
            logger.error(f"获取目录大小失败: {str(e)}")
            return 0

    @staticmethod
    def format_size(size_bytes: int) -> str:
        """
        格式化文件大小

        Args:
            size_bytes: 大小（字节）

        Returns:
            格式化后的大小字符串
        """
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024

        return f"{size_bytes:.2f} TB"

    @staticmethod
    def cleanup_by_size_limit(
        directory: Path,
        max_size_gb: float = 10.0,
    ) -> Tuple[bool, int, str]:
        """
        根据大小限制清理文件

        Args:
            directory: 目录路径
            max_size_gb: 最大大小限制（GB）

        Returns:
            (清理是否成功, 删除的文件数, 错误信息或成功消息)
        """
        try:
            directory = Path(directory)

            if not directory.exists():
                return True, 0, "目录不存在"

            # 获取目录大小
            current_size = ResourceCleanup.get_directory_size(directory)
            max_size_bytes = max_size_gb * 1024 * 1024 * 1024

            if current_size <= max_size_bytes:
                return True, 0, "目录大小在限制范围内"

            # 需要清理的大小
            need_to_free = current_size - max_size_bytes

            # 获取所有文件并按修改时间排序
            files = []
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    files.append(file_path)

            # 按修改时间排序（最旧的在前）
            files.sort(key=lambda x: os.path.getmtime(x))

            deleted_count = 0
            freed_size = 0

            # 删除文件直到达到目标大小
            for file_path in files:
                if freed_size >= need_to_free:
                    break

                try:
                    file_size = file_path.stat().st_size
                    file_path.unlink()
                    freed_size += file_size
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"删除文件失败: {file_path}, 错误: {str(e)}")

            logger.info(
                f"已清理 {deleted_count} 个文件，释放 {ResourceCleanup.format_size(freed_size)}"
            )

            return True, deleted_count, f"清理成功: 删除 {deleted_count} 个文件"

        except Exception as e:
            logger.error(f"清理文件失败: {str(e)}")
            return False, 0, f"清理失败: {str(e)}"
