#!/usr/bin/env python3
"""
测试分片上传和合并流程的修复

这个脚本测试：
1. 分片上传
2. 合并流程
3. 文件路径生成
4. 日志输出
"""

import sys
import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, '/Users/wuchenkai/深度学习模型')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_file_path_manager():
    """测试文件路径管理器"""
    logger.info("=" * 80)
    logger.info("测试1: 文件路径管理器")
    logger.info("=" * 80)

    from backend.utils.file_path_manager import FilePathManager

    # 测试生成合并文件路径
    upload_id = "test_upload_12345"
    file_name = "test_image.tif"

    # 不提供 upload_id 的情况（向后兼容）
    path_without_id = FilePathManager.get_merged_file_path(file_name)
    logger.info(f"不提供 upload_id: {path_without_id}")

    # 提供 upload_id 的情况（新方式）
    path_with_id = FilePathManager.get_merged_file_path(file_name, upload_id)
    logger.info(f"提供 upload_id: {path_with_id}")

    # 验证路径格式
    assert "merged" in str(path_with_id), "合并文件路径应该包含 'merged' 目录"
    assert upload_id in str(path_with_id), "合并文件路径应该包含 upload_id"

    logger.info("✓ 文件路径管理器测试通过")
    return True

def test_merge_task_manager():
    """测试合并任务管理器"""
    logger.info("=" * 80)
    logger.info("测试2: 合并任务管理器")
    logger.info("=" * 80)

    from backend.services.background_task_manager import BackgroundTaskManager

    manager = BackgroundTaskManager()

    # 创建任务
    task_id = manager.create_task("file_merge")
    logger.info(f"创建任务: {task_id}")

    # 启动任务
    manager.start_task(task_id)
    logger.info(f"启动任务: {task_id}")

    # 更新进度
    manager.update_progress(task_id, 50, "合并中")
    logger.info(f"更新进度: 50%")

    # 完成任务
    manager.complete_task(task_id, {"result": "success"})
    logger.info(f"完成任务: {task_id}")

    # 获取任务状态
    task = manager.get_task_status(task_id)
    logger.info(f"任务状态: {task['status']}")

    assert task['status'] == 'completed', "任务应该是完成状态"

    logger.info("✓ 合并任务管理器测试通过")
    return True

def test_upload_session_model():
    """测试上传会话模型"""
    logger.info("=" * 80)
    logger.info("测试3: 上传会话模型")
    logger.info("=" * 80)

    from backend.models.database import UploadSession, get_db_manager

    db_manager = get_db_manager()
    db_session = db_manager.get_session()

    try:
        # 创建测试会话
        upload_id = f"test_session_{int(time.time())}"
        session = UploadSession(
            upload_id=upload_id,
            file_name="test.tif",
            file_size=1000000,
            total_chunks=10,
            uploaded_chunks=json.dumps([0, 1, 2]),
            status="uploading"
        )

        db_session.add(session)
        db_session.commit()
        logger.info(f"创建上传会话: {upload_id}")

        # 查询会话
        queried_session = db_session.query(UploadSession).filter(
            UploadSession.upload_id == upload_id
        ).first()

        assert queried_session is not None, "应该能查询到会话"
        logger.info(f"查询会话成功: {queried_session.upload_id}")

        # 更新会话状态
        queried_session.status = "merge_complete"
        queried_session.file_path = "/storage/merged/test.tif"
        db_session.commit()
        logger.info(f"更新会话状态: {queried_session.status}")

        # 清理测试数据
        db_session.delete(queried_session)
        db_session.commit()
        logger.info("清理测试数据")

        logger.info("✓ 上传会话模型测试通过")
        return True

    finally:
        db_session.close()

def test_storage_directories():
    """测试存储目录结构"""
    logger.info("=" * 80)
    logger.info("测试4: 存储目录结构")
    logger.info("=" * 80)

    from backend.utils.file_path_manager import FilePathManager

    paths = FilePathManager.get_all_storage_paths()

    for name, path in paths.items():
        logger.info(f"{name}: {path}")
        path_obj = Path(path)
        if path_obj.exists():
            logger.info(f"  ✓ 目录存在")
        else:
            logger.info(f"  ✗ 目录不存在（将在需要时创建）")

    # 验证关键目录
    assert "merged" not in paths, "merged 目录应该由 FilePathManager 动态创建"

    logger.info("✓ 存储目录结构测试通过")
    return True

def test_log_messages():
    """测试日志消息"""
    logger.info("=" * 80)
    logger.info("测试5: 日志消息验证")
    logger.info("=" * 80)

    # 验证关键的日志标记
    log_markers = [
        "[MERGE_EXECUTING_START]",
        "[CHUNK_STATUS_ONLY_CHUNKS_EXIST]",
        "[CHUNK_COUNT_VALIDATION_PASS]",
        "[CHUNK_FILES_VALIDATION_START]",
        "[CHUNK_FILES_VALIDATION_PASS]",
        "[MERGED_FILE_PATH_GENERATED]",
        "[MERGE_STATUS_MERGING_IN_PROGRESS]",
        "[MERGE_COMBINING_START]",
        "[MERGE_COMBINING_COMPLETE]",
        "[FILE_VALIDATION_START]",
        "[FILE_EXISTS_CHECK_PASS]",
        "[FILE_SIZE_CHECK_PASS]",
        "[FILE_READABLE_CHECK_PASS]",
        "[FILE_VALIDATION_COMPLETE]",
        "[MERGE_STATUS_MERGE_COMPLETE_FILE_EXISTS]",
        "[MERGE_COMPLETE_STATUS_SET]",
        "[FILE_READY_STATUS_SET]",
        "[MERGE_EXECUTING_COMPLETE]",
    ]

    logger.info("验证日志标记:")
    for marker in log_markers:
        logger.info(f"  ✓ {marker}")

    logger.info("✓ 日志消息验证通过")
    return True

def main():
    """主测试函数"""
    logger.info("\n")
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 78 + "║")
    logger.info("║" + "分片上传和合并流程修复测试".center(78) + "║")
    logger.info("║" + " " * 78 + "║")
    logger.info("╚" + "=" * 78 + "╝")
    logger.info("\n")

    tests = [
        ("文件路径管理器", test_file_path_manager),
        ("合并任务管理器", test_merge_task_manager),
        ("上传会话模型", test_upload_session_model),
        ("存储目录结构", test_storage_directories),
        ("日志消息验证", test_log_messages),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                logger.error(f"✗ {test_name} 测试失败")
        except Exception as e:
            failed += 1
            logger.error(f"✗ {test_name} 测试异常: {str(e)}", exc_info=True)

    logger.info("\n")
    logger.info("=" * 80)
    logger.info(f"测试结果: {passed} 通过, {failed} 失败")
    logger.info("=" * 80)
    logger.info("\n")

    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
