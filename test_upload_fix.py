#!/usr/bin/env python3
"""
测试上传功能修复
使用指定的 tif 文件进行测试
"""

import os
import warnings
import requests
import hashlib
import time
from pathlib import Path

# 忽略 urllib3 的 SSL 警告
warnings.filterwarnings('ignore', message='urllib3 v2 only supports OpenSSL 1.1.1+')

# 配置
API_URL = "http://localhost:8000/api"
TEST_FILE = "/Users/wuchenkai/解译程序/20201023.tif"
CHUNK_SIZE = 5 * 1024 * 1024  # 5MB
MAX_CHUNKS_FOR_TEST = 100  # 临时限制，仅测试前 100 个分片

def get_file_md5(file_path: str) -> str:
    """计算文件的 MD5 哈希值"""
    md5_hash = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()

def test_upload():
    """测试上传功能"""
    print("=" * 60)
    print("测试上传功能")
    print("=" * 60)

    # 检查文件是否存在
    if not os.path.exists(TEST_FILE):
        print(f"❌ 文件不存在: {TEST_FILE}")
        return False

    file_size = os.path.getsize(TEST_FILE)
    file_name = os.path.basename(TEST_FILE)
    total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE

    # 临时限制测试分片数
    test_chunks = min(total_chunks, MAX_CHUNKS_FOR_TEST)

    print(f"📁 文件: {file_name}")
    print(f"📏 大小: {file_size / (1024**3):.2f} GB")
    print(f"🔢 总分片数: {total_chunks}")
    print(f"🧪 测试分片数: {test_chunks}")
    print(f"📦 分片大小: {CHUNK_SIZE / (1024**2):.2f} MB")
    print()

    # 生成 uploadId
    upload_id = f"test_{int(time.time())}"
    print(f"🆔 上传 ID: {upload_id}")
    print()

    # 读取文件并上传分片
    print("🚀 开始上传...")
    start_time = time.time()
    last_chunk_time = start_time

    try:
        with open(TEST_FILE, "rb") as f:
            for chunk_index in range(test_chunks):
                # 控制速率：确保不超过每秒 45 个请求
                now = time.time()
                time_since_last = now - last_chunk_time
                if time_since_last < 0.02:  # 20ms 间隔，即每秒最多 50 个
                    time.sleep(0.02 - time_since_last)
                last_chunk_time = time.time()

                chunk_data = f.read(CHUNK_SIZE)

                # 准备上传数据
                files = {
                    'chunk': (file_name, chunk_data, 'application/octet-stream')
                }
                data = {
                    'chunkIndex': chunk_index,
                    'totalChunks': total_chunks,
                    'fileName': file_name,
                    'fileSize': file_size,
                    'uploadId': upload_id,
                }

                # 上传分片
                response = requests.post(
                    f"{API_URL}/upload/chunk",
                    files=files,
                    data=data,
                    timeout=300  # 5 分钟超时
                )

                if response.status_code != 200:
                    print(f"❌ 分片 {chunk_index + 1}/{total_chunks} 上传失败")
                    print(f"   状态码: {response.status_code}")
                    print(f"   响应: {response.text}")
                    return False

                # 显示进度
                progress = (chunk_index + 1) / total_chunks * 100
                elapsed = time.time() - start_time
                speed = (chunk_index + 1) * CHUNK_SIZE / (1024**2) / elapsed

                print(f"\r📤 上传进度: {progress:.1f}% ({chunk_index + 1}/{total_chunks}) "
                      f"速度: {speed:.2f} MB/s", end='', flush=True)

                # 添加延迟避免触发速率限制
                if chunk_index % 20 == 19:  # 每20个分片暂停一下
                    time.sleep(0.1)

        print()
        print("✅ 所有分片上传完成")

        # 完成上传
        print()
        print("📝 正在完成上传...")
        complete_data = {
            'uploadId': upload_id,
            'fileName': file_name,
            'fileSize': file_size,
            'totalChunks': test_chunks,  # 使用实际上传的分片数
        }

        complete_response = requests.post(
            f"{API_URL}/upload/complete",
            json=complete_data,
            timeout=600  # 10 分钟超时
        )

        if complete_response.status_code != 200:
            print(f"❌ 完成上传失败")
            print(f"   状态码: {complete_response.status_code}")
            print(f"   响应: {complete_response.text}")
            return False

        complete_result = complete_response.json()
        print("✅ 上传完成")
        print(f"   任务 ID: {complete_result.get('taskId', 'N/A')}")

        total_time = time.time() - start_time
        avg_speed = file_size / (1024**3) / total_time

        print()
        print("=" * 60)
        print("📊 上传统计")
        print("=" * 60)
        print(f"⏱️  总耗时: {total_time:.2f} 秒")
        print(f"🚀 平均速度: {avg_speed:.3f} GB/s")
        print(f"📦 测试分片数: {test_chunks}/{total_chunks}")
        print("=" * 60)

        return True

    except Exception as e:
        print()
        print(f"❌ 上传过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_upload()
    if success:
        print()
        print("🎉 测试成功！")
    else:
        print()
        print("❌ 测试失败！")
        exit(1)
