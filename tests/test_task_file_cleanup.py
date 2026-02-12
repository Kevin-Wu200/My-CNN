"""
测试任务文件清理服务
"""

import pytest
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from backend.services.task_file_cleanup import TaskFileCleanupService
from backend.utils.file_path_manager import FilePathManager


class TestTaskFileCleanupService:
    """测试任务文件清理服务"""

    def test_validate_file_path_for_cleanup_valid_merged_file(self, tmp_path):
        """测试验证 merged 目录中的文件路径"""
        # 创建临时存储目录结构
        storage_root = tmp_path / "storage"
        merged_dir = storage_root / "merged"
        merged_dir.mkdir(parents=True)

        # 创建测试文件
        test_file = merged_dir / "test.tif"
        test_file.write_text("test")

        # Mock FilePathManager
        with patch.object(FilePathManager, 'get_storage_root', return_value=storage_root):
            with patch.object(FilePathManager, 'validate_path_is_in_storage', return_value=True):
                result = TaskFileCleanupService._validate_file_path_for_cleanup(test_file)
                assert result is True

    def test_validate_file_path_for_cleanup_valid_detection_images_file(self, tmp_path):
        """测试验证 detection_images 目录中的文件路径"""
        # 创建临时存储目录结构
        storage_root = tmp_path / "storage"
        detection_dir = storage_root / "detection_images"
        detection_dir.mkdir(parents=True)

        # 创建测试文件
        test_file = detection_dir / "test.tif"
        test_file.write_text("test")

        # Mock FilePathManager
        with patch.object(FilePathManager, 'get_storage_root', return_value=storage_root):
            with patch.object(FilePathManager, 'validate_path_is_in_storage', return_value=True):
                result = TaskFileCleanupService._validate_file_path_for_cleanup(test_file)
                assert result is True

    def test_validate_file_path_for_cleanup_forbidden_models_dir(self, tmp_path):
        """测试禁止删除 models 目录中的文件"""
        # 创建临时存储目录结构
        storage_root = tmp_path / "storage"
        models_dir = storage_root / "models"
        models_dir.mkdir(parents=True)

        # 创建测试文件
        test_file = models_dir / "model.pth"
        test_file.write_text("test")

        # Mock FilePathManager
        with patch.object(FilePathManager, 'get_storage_root', return_value=storage_root):
            with patch.object(FilePathManager, 'validate_path_is_in_storage', return_value=True):
                result = TaskFileCleanupService._validate_file_path_for_cleanup(test_file)
                assert result is False

    def test_validate_file_path_for_cleanup_file_not_exists(self, tmp_path):
        """测试文件不存在时的验证"""
        # 创建临时存储目录结构
        storage_root = tmp_path / "storage"
        merged_dir = storage_root / "merged"
        merged_dir.mkdir(parents=True)

        # 不创建文件，直接测试
        test_file = merged_dir / "nonexistent.tif"

        # Mock FilePathManager
        with patch.object(FilePathManager, 'get_storage_root', return_value=storage_root):
            with patch.object(FilePathManager, 'validate_path_is_in_storage', return_value=True):
                result = TaskFileCleanupService._validate_file_path_for_cleanup(test_file)
                assert result is False

    def test_safe_delete_file_success(self, tmp_path):
        """测试成功删除文件"""
        # 创建临时存储目录结构
        storage_root = tmp_path / "storage"
        merged_dir = storage_root / "merged"
        merged_dir.mkdir(parents=True)

        # 创建测试文件
        test_file = merged_dir / "test.tif"
        test_file.write_text("test")

        # Mock FilePathManager
        with patch.object(FilePathManager, 'get_storage_root', return_value=storage_root):
            with patch.object(FilePathManager, 'validate_path_is_in_storage', return_value=True):
                result = TaskFileCleanupService._safe_delete_file(test_file)
                assert result is True
                assert not test_file.exists()

    def test_safe_delete_file_validation_failed(self, tmp_path):
        """测试验证失败时不删除文件"""
        # 创建临时存储目录结构
        storage_root = tmp_path / "storage"
        models_dir = storage_root / "models"
        models_dir.mkdir(parents=True)

        # 创建测试文件
        test_file = models_dir / "model.pth"
        test_file.write_text("test")

        # Mock FilePathManager
        with patch.object(FilePathManager, 'get_storage_root', return_value=storage_root):
            with patch.object(FilePathManager, 'validate_path_is_in_storage', return_value=True):
                result = TaskFileCleanupService._safe_delete_file(test_file)
                assert result is False
                assert test_file.exists()  # 文件应该仍然存在

    def test_find_related_files_with_valid_task_result(self, tmp_path):
        """测试查找相关文件"""
        # 创建临时存储目录结构
        storage_root = tmp_path / "storage"
        detection_dir = storage_root / "detection_images"
        merged_dir = storage_root / "merged"
        detection_dir.mkdir(parents=True)
        merged_dir.mkdir(parents=True)

        # 创建测试文件
        detection_file = detection_dir / "test.tif"
        detection_file.write_text("test")
        merged_file = merged_dir / "upload123.tif"
        merged_file.write_text("test")

        # Mock 数据库查询
        mock_session = MagicMock()
        mock_upload_session = MagicMock()
        mock_upload_session.upload_id = "upload123"
        mock_upload_session.file_name = "test.tif"
        mock_upload_session.file_path = str(merged_file)
        mock_upload_session.status = "completed"
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_upload_session]

        mock_db_manager = MagicMock()
        mock_db_manager.get_session.return_value = mock_session

        # Mock FilePathManager
        with patch.object(FilePathManager, 'get_detection_images_dir', return_value=detection_dir):
            with patch('backend.services.task_file_cleanup.get_db_manager', return_value=mock_db_manager):
                task_result = {"image_path": str(detection_file)}
                related_files = TaskFileCleanupService._find_related_files(task_result)

                assert len(related_files) == 2
                assert detection_file in related_files
                assert merged_file in related_files

    def test_schedule_cleanup_creates_thread(self):
        """测试调度清理创建后台线程"""
        task_id = "test-task-123"
        task_result = {"image_path": "/path/to/image.tif"}

        with patch('backend.services.task_file_cleanup.threading.Thread') as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance

            TaskFileCleanupService.schedule_cleanup(task_id, task_result, delay_seconds=1)

            # 验证线程被创建和启动
            mock_thread.assert_called_once()
            mock_thread_instance.start.assert_called_once()

    def test_cleanup_task_files_with_no_files(self):
        """测试没有文件需要清理的情况"""
        task_id = "test-task-123"
        task_result = {"image_path": "/nonexistent/image.tif"}

        with patch.object(TaskFileCleanupService, '_find_related_files', return_value=[]):
            # 应该不会抛出异常
            TaskFileCleanupService._cleanup_task_files(task_id, task_result)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
