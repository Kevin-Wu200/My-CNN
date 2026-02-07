"""
文件路径管理模块

第7步：统一上传阶段与处理阶段使用的文件路径来源
- 将文件根目录集中在一个配置位置
- 禁止在不同模块中各自拼接路径
- 提供统一的路径获取接口
"""

from pathlib import Path
from typing import Optional
import logging

from backend.config.settings import (
    STORAGE_DIR,
    UPLOAD_DIR,
    TRAINING_SAMPLES_DIR,
    DETECTION_IMAGES_DIR,
    TEMP_DIR,
    MODELS_DIR,
)

logger = logging.getLogger(__name__)


class FilePathManager:
    """
    统一的文件路径管理器

    所有文件路径操作都应该通过此类进行，确保路径来源一致
    """

    # 文件根目录配置（集中在一个位置）
    _STORAGE_ROOT = STORAGE_DIR
    _UPLOAD_ROOT = UPLOAD_DIR
    _TRAINING_SAMPLES_ROOT = TRAINING_SAMPLES_DIR
    _DETECTION_IMAGES_ROOT = DETECTION_IMAGES_DIR
    _TEMP_ROOT = TEMP_DIR
    _MODELS_ROOT = MODELS_DIR

    @classmethod
    def get_storage_root(cls) -> Path:
        """获取存储根目录"""
        return cls._STORAGE_ROOT

    @classmethod
    def get_upload_dir(cls) -> Path:
        """获取上传文件目录"""
        return cls._UPLOAD_ROOT

    @classmethod
    def get_training_samples_dir(cls) -> Path:
        """获取训练样本目录"""
        return cls._TRAINING_SAMPLES_ROOT

    @classmethod
    def get_detection_images_dir(cls) -> Path:
        """获取检测影像目录"""
        return cls._DETECTION_IMAGES_ROOT

    @classmethod
    def get_temp_dir(cls) -> Path:
        """获取临时文件目录"""
        return cls._TEMP_ROOT

    @classmethod
    def get_models_dir(cls) -> Path:
        """获取模型目录"""
        return cls._MODELS_ROOT

    @classmethod
    def get_chunk_dir(cls, upload_id: str) -> Path:
        """
        获取分片存储目录

        Args:
            upload_id: 上传会话ID

        Returns:
            分片目录路径
        """
        chunk_dir = cls._TEMP_ROOT / upload_id
        return chunk_dir

    @classmethod
    def get_chunk_path(cls, upload_id: str, chunk_index: int) -> Path:
        """
        获取单个分片文件路径

        Args:
            upload_id: 上传会话ID
            chunk_index: 分片索引

        Returns:
            分片文件路径
        """
        chunk_path = cls.get_chunk_dir(upload_id) / f"chunk_{chunk_index}"
        return chunk_path

    @classmethod
    def get_merged_file_path(cls, file_name: str, upload_id: str = None) -> Path:
        """
        获取合并后的文件路径

        第4步：生成唯一的完整tif文件路径
        - 如果提供了upload_id，使用 storage/merged/{uploadId}.tif 格式
        - 否则使用 storage/detection_images/{file_name} 格式（向后兼容）

        Args:
            file_name: 文件名
            upload_id: 上传会话ID（可选，用于生成唯一路径）

        Returns:
            合并后的文件路径
        """
        if upload_id:
            # 第4步：生成唯一的完整tif文件路径
            merged_dir = cls._STORAGE_ROOT / "merged"
            cls.ensure_directory_exists(merged_dir)
            # 使用uploadId作为文件名，保留原始文件的扩展名
            file_ext = Path(file_name).suffix or ".tif"
            merged_path = merged_dir / f"{upload_id}{file_ext}"
        else:
            # 向后兼容：如果没有提供upload_id，使用原始逻辑
            merged_path = cls._DETECTION_IMAGES_ROOT / file_name
        return merged_path

    @classmethod
    def validate_path_is_in_storage(cls, file_path: str) -> bool:
        """
        验证文件路径是否在存储目录内

        防止路径遍历攻击

        Args:
            file_path: 文件路径

        Returns:
            是否在存储目录内
        """
        try:
            file_path_obj = Path(file_path).resolve()
            storage_root = cls._STORAGE_ROOT.resolve()

            # 检查文件路径是否在存储根目录下
            file_path_obj.relative_to(storage_root)
            return True
        except ValueError:
            logger.warning(f"[PATH_VALIDATION_FAILED] 文件路径不在存储目录内: {file_path}")
            return False

    @classmethod
    def ensure_directory_exists(cls, directory: Path) -> None:
        """
        确保目录存在

        Args:
            directory: 目录路径
        """
        directory.mkdir(parents=True, exist_ok=True)
        logger.debug(f"[DIRECTORY_ENSURED] {directory}")

    @classmethod
    def get_all_storage_paths(cls) -> dict:
        """
        获取所有存储路径配置

        用于调试和配置验证

        Returns:
            所有存储路径的字典
        """
        return {
            "storage_root": str(cls._STORAGE_ROOT),
            "upload_dir": str(cls._UPLOAD_ROOT),
            "training_samples_dir": str(cls._TRAINING_SAMPLES_ROOT),
            "detection_images_dir": str(cls._DETECTION_IMAGES_ROOT),
            "temp_dir": str(cls._TEMP_ROOT),
            "models_dir": str(cls._MODELS_ROOT),
        }
