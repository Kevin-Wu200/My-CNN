"""
解压服务模块
用于处理 ZIP 和 RAR 压缩包的解压操作
"""

import os
import shutil
import zipfile
import rarfile
from pathlib import Path
from typing import Tuple, List
import logging

logger = logging.getLogger(__name__)


class DecompressionService:
    """压缩包解压服务类"""

    def __init__(self, temp_dir: Path):
        """
        初始化解压服务

        Args:
            temp_dir: 临时目录路径
        """
        self.temp_dir = temp_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def decompress_file(self, file_path: str) -> Tuple[bool, str, Path]:
        """
        解压压缩文件（支持 ZIP 和 RAR）

        Args:
            file_path: 压缩文件路径

        Returns:
            (成功标志, 错误信息或成功消息, 解压目录路径)
        """
        try:
            file_path = Path(file_path)

            # 检查文件是否存在
            if not file_path.exists():
                return False, f"压缩文件不存在: {file_path}", None

            # 获取文件扩展名
            file_ext = file_path.suffix.lower()

            # 创建解压目录
            extract_dir = self.temp_dir / file_path.stem
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            extract_dir.mkdir(parents=True, exist_ok=True)

            # 根据文件类型选择解压方式
            if file_ext == ".zip":
                success, message = self._decompress_zip(file_path, extract_dir)
            elif file_ext == ".rar":
                success, message = self._decompress_rar(file_path, extract_dir)
            else:
                return False, f"不支持的压缩格式: {file_ext}", None

            if not success:
                # 解压失败，清理目录
                if extract_dir.exists():
                    shutil.rmtree(extract_dir)
                return False, message, None

            return True, "解压成功", extract_dir

        except Exception as e:
            logger.error(f"解压文件时出错: {str(e)}")
            return False, f"解压失败: {str(e)}", None

    def _decompress_zip(self, zip_path: Path, extract_dir: Path) -> Tuple[bool, str]:
        """
        解压 ZIP 文件

        Args:
            zip_path: ZIP 文件路径
            extract_dir: 解压目录

        Returns:
            (成功标志, 错误信息或成功消息)
        """
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            return True, "ZIP 文件解压成功"
        except zipfile.BadZipFile:
            return False, "ZIP 文件格式错误或已损坏"
        except Exception as e:
            return False, f"ZIP 解压失败: {str(e)}"

    def _decompress_rar(self, rar_path: Path, extract_dir: Path) -> Tuple[bool, str]:
        """
        解压 RAR 文件

        Args:
            rar_path: RAR 文件路径
            extract_dir: 解压目录

        Returns:
            (成功标志, 错误信息或成功消息)
        """
        try:
            with rarfile.RarFile(rar_path, 'r') as rar_ref:
                rar_ref.extractall(extract_dir)
            return True, "RAR 文件解压成功"
        except rarfile.BadRarFile:
            return False, "RAR 文件格式错误或已损坏"
        except Exception as e:
            return False, f"RAR 解压失败: {str(e)}"

    def cleanup_temp_dir(self, extract_dir: Path) -> bool:
        """
        清理临时解压目录

        Args:
            extract_dir: 要清理的目录路径

        Returns:
            清理是否成功
        """
        try:
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            return True
        except Exception as e:
            logger.error(f"清理临时目录失败: {str(e)}")
            return False

    def get_extracted_files(self, extract_dir: Path) -> List[Path]:
        """
        获取解压目录中的所有文件

        Args:
            extract_dir: 解压目录

        Returns:
            文件路径列表
        """
        files = []
        if extract_dir.exists():
            for file_path in extract_dir.rglob("*"):
                if file_path.is_file():
                    files.append(file_path)
        return sorted(files)
