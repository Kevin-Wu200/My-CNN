#!/usr/bin/env python3
"""
分片上传功能测试脚本
测试前端并发控制和后端限流机制
"""

import os
import sys
import time
import requests
import json
from pathlib import Path
from datetime import datetime

# 项目根目录
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# 后端 API 地址
API_BASE_URL = "http://localhost:8000/api"
CHUNK_SIZE = 5 * 1024 * 1024  # 5MB

def create_test_file(size_mb: int = 50) -> Path:
    """创建测试文件"""
    test_file = PROJECT_ROOT / "test_file.bin"
    print(f"创建 {size_mb}MB 测试文件: {test_file}")

    with open(test_file, "wb") as f:
        # 写入指定大小的数据
        chunk = b"x" * (1024 * 1024)  # 1MB 块
        for _ in range(size_mb):
            f.write(chunk)

    print(f"测试文件创建完成，大小: {test_file.stat().st_size / (1024*1024):.2f}MB")
    return test_file

def upload_file(file_path: Path, upload_id: str = None) -> dict:
    """上传文件"""
    if upload_id is None:
        upload_id = f"test_{int(time.time() * 1000)}"

    file_size = file_path.stat().st_size
    total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE

    print(f"\n开始上传文件: {file_path.name}")
    print(f"文件大小: {file_size / (1024*1024):.2f}MB")
    print(f"总分片数: {total_chunks}")
    print(f"上传ID: {upload_id}")

    # 分片上传
    uploaded_chunks = 0
    start_time = time.time()

    for chunk_index in range(total_chunks):
        offset = chunk_index * CHUNK_SIZE
        end = min(offset + CHUNK_SIZE, file_size)

        with open(file_path, "rb") as f:
            f.seek(offset)
            chunk_data = f.read(end - offset)

        # 上传分片
        files = {
            'chunk': ('chunk', chunk_data),
        }
        data = {
            'chunkIndex': chunk_index,
            'totalChunks': total_chunks,
            'fileName': file_path.name,
            'fileSize': file_size,
            'uploadId': upload_id,
        }

        try:
            response = requests.post(
                f"{API_BASE_URL}/upload/chunk",
                files=files,
                data=data,
                timeout=60
            )

            if response.status_code == 429:
                print(f"  分片 {chunk_index}: 被限流，等待后重试...")
                time.sleep(2)
                # 重试
                response = requests.post(
                    f"{API_BASE_URL}/upload/chunk",
                    files=files,
                    data=data,
                    timeout=60
                )

            if response.status_code == 200:
                result = response.json()
                uploaded_chunks = result.get('uploadedChunks', 0)
                progress = result.get('progress', 0)
                print(f"  分片 {chunk_index}: 成功 (进度: {progress}%)")
            else:
                print(f"  分片 {chunk_index}: 失败 (状态码: {response.status_code})")
                print(f"    错误: {response.text}")
                return {"status": "failed", "error": response.text}

        except Exception as e:
            print(f"  分片 {chunk_index}: 异常 - {str(e)}")
            return {"status": "failed", "error": str(e)}

    # 完成上传
    print(f"\n所有分片上传完成，正在提交合并任务...")

    try:
        response = requests.post(
            f"{API_BASE_URL}/upload/complete",
            json={
                'uploadId': upload_id,
                'fileName': file_path.name,
                'fileSize': file_size,
                'totalChunks': total_chunks,
            },
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            print(f"合并任务已提交: {result.get('taskId')}")

            # 轮询查询状态
            print("\n等待文件合并完成...")
            max_wait = 300  # 5分钟
            wait_time = 0

            while wait_time < max_wait:
                time.sleep(2)
                wait_time += 2

                status_response = requests.get(
                    f"{API_BASE_URL}/upload/status/{upload_id}",
                    timeout=10
                )

                if status_response.status_code == 200:
                    status = status_response.json()
                    print(f"  状态: {status['status']}, 进度: {status['progress']}%")

                    if status['status'] == 'completed':
                        elapsed = time.time() - start_time
                        print(f"\n上传完成！")
                        print(f"  文件路径: {status['filePath']}")
                        print(f"  总耗时: {elapsed:.2f}秒")
                        return {
                            "status": "success",
                            "uploadId": upload_id,
                            "filePath": status['filePath'],
                            "elapsed": elapsed
                        }
                    elif status['status'] == 'failed':
                        print(f"上传失败: {status.get('errorMessage')}")
                        return {
                            "status": "failed",
                            "error": status.get('errorMessage')
                        }

            print(f"等待超时（{max_wait}秒）")
            return {"status": "timeout"}
        else:
            print(f"提交合并任务失败: {response.status_code}")
            print(f"错误: {response.text}")
            return {"status": "failed", "error": response.text}

    except Exception as e:
        print(f"提交合并任务异常: {str(e)}")
        return {"status": "failed", "error": str(e)}

def main():
    """主测试函数"""
    print("=" * 60)
    print("分片上传功能测试")
    print("=" * 60)

    # 检查后端是否运行
    try:
        response = requests.get(f"{API_BASE_URL}/upload/status/test", timeout=5)
    except Exception as e:
        print(f"错误: 无法连接到后端 API ({API_BASE_URL})")
        print(f"请确保后端服务已启动")
        return

    # 创建测试文件
    test_file = create_test_file(size_mb=50)  # 50MB 测试文件

    try:
        # 执行上传测试
        result = upload_file(test_file)

        print("\n" + "=" * 60)
        print("测试结果:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("=" * 60)

        if result['status'] == 'success':
            print("✓ 测试通过")
        else:
            print("✗ 测试失败")

    finally:
        # 清理测试文件
        if test_file.exists():
            test_file.unlink()
            print(f"\n清理测试文件: {test_file}")

if __name__ == "__main__":
    main()
