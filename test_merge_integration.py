#!/usr/bin/env python3
"""
集成测试：分片上传、合并和检测的完整流程

这个脚本测试：
1. 创建小的测试文件
2. 分片上传
3. 合并流程
4. 验证合并后的文件
5. 检测流程
"""

import sys
import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime
import shutil

# 添加项目路径
sys.path.insert(0, '/Users/wuchenkai/深度学习模型')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_test_file(size_mb=10):
    """创建测试文件"""
    logger.info(f"创建 {size_mb}MB 的测试文件")

    test_file = Path("/tmp/test_image.bin")
    with open(test_file, "wb") as f:
        # 写入指定大小的数据
        chunk_size = 1024 * 1024  # 1MB
        for i in range(size_mb):
            f.write(b"X" * chunk_size)

    logger.info(f"测试文件创建完成: {test_file}, 大小: {test_file.stat().st_size} 字节")
    return test_file

def test_chunk_upload_and_merge():
    """测试分片上传和合并"""
    logger.info("=" * 80)
    logger.info("集成测试: 分片上传和合并流程")
    logger.info("=" * 80)

    from backend.utils.file_path_manager import FilePathManager
    from backend.models.database import UploadSession, get_db_manager
    from backend.services.background_task_manager import BackgroundTaskManager

    # 创建测试文件
    test_file = create_test_file(size_mb=5)
    file_size = test_file.stat().st_size

    # 分片参数
    chunk_size = 1024 * 1024  # 1MB
    total_chunks = (file_size + chunk_size - 1) // chunk_size
    upload_id = f"test_upload_{int(time.time())}"
    file_name = "test_image.bin"

    logger.info(f"分片参数: uploadId={upload_id}, totalChunks={total_chunks}, fileSize={file_size}")

    # 创建分片目录
    chunk_dir = FilePathManager.get_chunk_dir(upload_id)
    FilePathManager.ensure_directory_exists(chunk_dir)
    logger.info(f"分片目录: {chunk_dir}")

    # 上传分片
    logger.info("开始上传分片...")
    with open(test_file, "rb") as f:
        for i in range(total_chunks):
            chunk_data = f.read(chunk_size)
            chunk_path = FilePathManager.get_chunk_path(upload_id, i)

            with open(chunk_path, "wb") as chunk_file:
                chunk_file.write(chunk_data)

            logger.info(f"  分片 {i}/{total_chunks} 上传完成: {len(chunk_data)} 字节")

    # 创建上传会话
    db_manager = get_db_manager()
    db_session = db_manager.get_session()

    try:
        upload_session = UploadSession(
            upload_id=upload_id,
            file_name=file_name,
            file_size=file_size,
            total_chunks=total_chunks,
            uploaded_chunks=json.dumps(list(range(total_chunks))),
            status="chunks_complete"
        )
        db_session.add(upload_session)
        db_session.commit()
        logger.info(f"上传会话创建完成: {upload_id}")
    finally:
        db_session.close()

    # 执行合并
    logger.info("开始执行合并...")
    task_manager = BackgroundTaskManager()
    task_id = task_manager.submit_merge_task(
        uploadId=upload_id,
        fileName=file_name,
        fileSize=file_size,
        totalChunks=total_chunks,
    )
    logger.info(f"合并任务提交: taskId={task_id}")

    # 等待合并完成
    logger.info("等待合并完成...")
    max_wait = 30  # 最多等待30秒
    start_time = time.time()
    while time.time() - start_time < max_wait:
        task = task_manager.get_task_status(task_id)
        if task and task['status'] == 'completed':
            logger.info(f"合并完成: {task}")
            break
        elif task and task['status'] == 'failed':
            logger.error(f"合并失败: {task}")
            return False
        time.sleep(1)
    else:
        logger.error("合并超时")
        return False

    # 验证合并后的文件
    logger.info("验证合并后的文件...")
    merged_path = FilePathManager.get_merged_file_path(file_name, upload_id)
    logger.info(f"合并文件路径: {merged_path}")

    if not merged_path.exists():
        logger.error(f"合并文件不存在: {merged_path}")
        return False

    merged_size = merged_path.stat().st_size
    logger.info(f"合并文件大小: {merged_size} 字节")

    if merged_size != file_size:
        logger.error(f"文件大小不匹配: 期望 {file_size}, 实际 {merged_size}")
        return False

    # 验证文件内容
    logger.info("验证文件内容...")
    with open(test_file, "rb") as f1, open(merged_path, "rb") as f2:
        original_data = f1.read()
        merged_data = f2.read()

        if original_data == merged_data:
            logger.info("✓ 文件内容验证通过")
        else:
            logger.error("✗ 文件内容不匹配")
            return False

    # 验证数据库状态
    logger.info("验证数据库状态...")
    db_session = db_manager.get_session()
    try:
        upload_session = db_session.query(UploadSession).filter(
            UploadSession.upload_id == upload_id
        ).first()

        if not upload_session:
            logger.error(f"上传会话不存在: {upload_id}")
            return False

        logger.info(f"上传会话状态: {upload_session.status}")
        logger.info(f"合并文件路径: {upload_session.file_path}")

        if upload_session.status != "completed":
            logger.error(f"上传会话状态不正确: {upload_session.status}")
            return False

        if upload_session.file_path != str(merged_path):
            logger.error(f"文件路径不匹配: {upload_session.file_path} != {merged_path}")
            return False

        logger.info("✓ 数据库状态验证通过")
    finally:
        db_session.close()

    # 清理测试文件
    logger.info("清理测试文件...")
    test_file.unlink()
    shutil.rmtree(chunk_dir, ignore_errors=True)

    logger.info("✓ 集成测试通过")
    return True

def test_file_readiness_check():
    """测试文件就绪检查"""
    logger.info("=" * 80)
    logger.info("测试: 文件就绪检查")
    logger.info("=" * 80)

    from backend.api.unsupervised_detection import check_file_readiness
    from backend.models.database import UploadSession, get_db_manager
    from backend.utils.file_path_manager import FilePathManager

    # 创建测试文件
    test_file = Path("/tmp/test_readiness.bin")
    test_file.write_bytes(b"test data")

    # 创建上传会话
    upload_id = f"test_readiness_{int(time.time())}"
    db_manager = get_db_manager()
    db_session = db_manager.get_session()

    try:
        upload_session = UploadSession(
            upload_id=upload_id,
            file_name="test_readiness.bin",
            file_size=9,
            total_chunks=1,
            uploaded_chunks=json.dumps([0]),
            status="completed",
            file_path=str(test_file)
        )
        db_session.add(upload_session)
        db_session.commit()
        logger.info(f"创建测试上传会话: {upload_id}")
    finally:
        db_session.close()

    # 测试文件就绪检查
    logger.info("测试1: 文件存在且状态为 completed")
    is_ready, error_msg = check_file_readiness(str(test_file))
    if is_ready:
        logger.info("✓ 文件就绪检查通过")
    else:
        logger.error(f"✗ 文件就绪检查失败: {error_msg}")
        return False

    # 测试文件不存在的情况
    logger.info("测试2: 文件不存在")
    is_ready, error_msg = check_file_readiness("/tmp/nonexistent_file.bin")
    if not is_ready:
        logger.info(f"✓ 正确拒绝不存在的文件: {error_msg}")
    else:
        logger.error("✗ 应该拒绝不存在的文件")
        return False

    # 清理
    test_file.unlink()
    db_session = db_manager.get_session()
    try:
        upload_session = db_session.query(UploadSession).filter(
            UploadSession.upload_id == upload_id
        ).first()
        if upload_session:
            db_session.delete(upload_session)
            db_session.commit()
    finally:
        db_session.close()

    logger.info("✓ 文件就绪检查测试通过")
    return True

def main():
    """主测试函数"""
    logger.info("\n")
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 78 + "║")
    logger.info("║" + "分片上传、合并和检测集成测试".center(78) + "║")
    logger.info("║" + " " * 78 + "║")
    logger.info("╚" + "=" * 78 + "╝")
    logger.info("\n")

    tests = [
        ("分片上传和合并流程", test_chunk_upload_and_merge),
        ("文件就绪检查", test_file_readiness_check),
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
    logger.info(f"集成测试结果: {passed} 通过, {failed} 失败")
    logger.info("=" * 80)
    logger.info("\n")

    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
