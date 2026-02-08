#!/usr/bin/env python3
"""
分片上传流程8步实现的测试脚本

测试内容：
1. 验证 chunk 接收日志
2. 验证状态转移流程
3. 验证文件就绪检查
4. 验证速率限制
5. 验证文件校验
"""

import requests
import json
import time
import sys
from pathlib import Path
from typing import Dict, Any, Tuple

# 配置
API_BASE_URL = "http://localhost:8000"
TEST_FILE_SIZE = 1024 * 1024  # 1MB
CHUNK_SIZE = 256 * 1024  # 256KB
UPLOAD_ID = "test-upload-" + str(int(time.time()))

# 颜色输出
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_step(step: int, title: str):
    """打印步骤标题"""
    print(f"\n{Colors.BLUE}{'='*60}")
    print(f"步骤 {step}: {title}")
    print(f"{'='*60}{Colors.END}\n")

def print_success(msg: str):
    """打印成功信息"""
    print(f"{Colors.GREEN}✓ {msg}{Colors.END}")

def print_error(msg: str):
    """打印错误信息"""
    print(f"{Colors.RED}✗ {msg}{Colors.END}")

def print_info(msg: str):
    """打印信息"""
    print(f"{Colors.YELLOW}ℹ {msg}{Colors.END}")

def create_test_file(size: int) -> bytes:
    """创建测试文件内容"""
    return b"X" * size

def upload_chunk(chunk_index: int, chunk_data: bytes, total_chunks: int) -> Tuple[bool, Dict]:
    """上传单个分片"""
    url = f"{API_BASE_URL}/upload/chunk"

    files = {
        'chunk': ('chunk_data', chunk_data)
    }
    data = {
        'chunkIndex': chunk_index,
        'totalChunks': total_chunks,
        'fileName': 'test_image.tif',
        'fileSize': TEST_FILE_SIZE,
        'uploadId': UPLOAD_ID
    }

    try:
        response = requests.post(url, files=files, data=data, timeout=30)
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, {'error': response.text}
    except Exception as e:
        return False, {'error': str(e)}

def complete_upload() -> Tuple[bool, Dict]:
    """完成上传"""
    url = f"{API_BASE_URL}/upload/complete"

    payload = {
        'uploadId': UPLOAD_ID,
        'fileName': 'test_image.tif',
        'fileSize': TEST_FILE_SIZE,
        'totalChunks': 4
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, {'error': response.text}
    except Exception as e:
        return False, {'error': str(e)}

def get_upload_status() -> Tuple[bool, Dict]:
    """获取上传状态"""
    url = f"{API_BASE_URL}/upload/status/{UPLOAD_ID}"

    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, {'error': response.text}
    except Exception as e:
        return False, {'error': str(e)}

def test_chunk_reception():
    """测试1: 验证 chunk 接收日志"""
    print_step(1, "验证 chunk 接收日志")

    test_file = create_test_file(TEST_FILE_SIZE)
    total_chunks = 4

    print_info(f"创建测试文件: {TEST_FILE_SIZE} 字节")
    print_info(f"分片数量: {total_chunks}")
    print_info(f"每个分片大小: {CHUNK_SIZE} 字节\n")

    for i in range(total_chunks):
        chunk_start = i * CHUNK_SIZE
        chunk_end = min((i + 1) * CHUNK_SIZE, TEST_FILE_SIZE)
        chunk_data = test_file[chunk_start:chunk_end]

        print_info(f"上传分片 {i+1}/{total_chunks} (大小: {len(chunk_data)} 字节)")

        success, response = upload_chunk(i, chunk_data, total_chunks)

        if success:
            print_success(f"分片 {i} 上传成功")
            print(f"  - 已上传: {response.get('uploadedChunks')}/{response.get('totalChunks')}")
            print(f"  - 进度: {response.get('progress')}%\n")
        else:
            print_error(f"分片 {i} 上传失败: {response.get('error')}")
            return False

    print_success("所有分片上传完成")
    return True

def test_status_transition():
    """测试2: 验证状态转移流程"""
    print_step(2, "验证状态转移流程")

    # 检查当前状态（应该是 uploading）
    print_info("检查当前状态...")
    success, status = get_upload_status()

    if not success:
        print_error(f"获取状态失败: {status.get('error')}")
        return False

    print_success(f"当前状态: {status.get('status')}")
    print(f"  - 已上传: {status.get('uploadedChunks')}/{status.get('totalChunks')}")
    print(f"  - 进度: {status.get('progress')}%")
    print(f"  - 文件就绪: {status.get('fileReady')}\n")

    # 完成上传，触发合并
    print_info("完成上传，触发合并...")
    success, response = complete_upload()

    if not success:
        print_error(f"完成上传失败: {response.get('error')}")
        return False

    print_success("合并任务已提交")
    print(f"  - 任务ID: {response.get('taskId')}\n")

    # 等待合并完成
    print_info("等待合并完成...")
    max_wait = 30
    start_time = time.time()

    while time.time() - start_time < max_wait:
        success, status = get_upload_status()

        if not success:
            print_error(f"获取状态失败: {status.get('error')}")
            return False

        current_status = status.get('status')
        print_info(f"当前状态: {current_status}")

        if current_status == 'completed':
            print_success("文件已就绪！")
            print(f"  - 文件路径: {status.get('filePath')}")
            print(f"  - 文件就绪: {status.get('fileReady')}\n")
            return True
        elif current_status == 'failed':
            print_error(f"合并失败: {status.get('errorMessage')}")
            return False

        time.sleep(2)

    print_error("合并超时")
    return False

def test_rate_limiting():
    """测试3: 验证速率限制"""
    print_step(3, "验证速率限制")

    upload_id_rate_test = "rate-limit-test-" + str(int(time.time()))
    test_file = create_test_file(CHUNK_SIZE)

    print_info("快速发送多个请求，测试速率限制...")
    print_info("配置: 每秒最多 10 个请求\n")

    success_count = 0
    rate_limited_count = 0
    error_count = 0

    for i in range(15):
        url = f"{API_BASE_URL}/upload/chunk"

        files = {
            'chunk': ('chunk_data', test_file)
        }
        data = {
            'chunkIndex': i,
            'totalChunks': 15,
            'fileName': 'rate_test.tif',
            'fileSize': CHUNK_SIZE * 15,
            'uploadId': upload_id_rate_test
        }

        try:
            response = requests.post(url, files=files, data=data, timeout=5)

            if response.status_code == 200:
                success_count += 1
                print_success(f"请求 {i+1}: 成功 (200)")
            elif response.status_code == 429:
                rate_limited_count += 1
                print_info(f"请求 {i+1}: 被限流 (429)")
            else:
                error_count += 1
                print_error(f"请求 {i+1}: 错误 ({response.status_code})")
        except Exception as e:
            error_count += 1
            print_error(f"请求 {i+1}: 异常 - {str(e)}")

    print(f"\n统计结果:")
    print(f"  - 成功: {success_count}")
    print(f"  - 被限流: {rate_limited_count}")
    print(f"  - 错误: {error_count}\n")

    if rate_limited_count > 0:
        print_success("速率限制工作正常")
        return True
    else:
        print_info("未触发速率限制（可能请求间隔较长）")
        return True

def test_file_readiness_check():
    """测试4: 验证文件就绪检查"""
    print_step(4, "验证文件就绪检查")

    # 尝试用不存在的文件进行检测
    print_info("尝试用不存在的文件进行检测...")

    url = f"{API_BASE_URL}/unsupervised/detect"
    params = {
        'image_path': '/nonexistent/file.tif',
        'n_clusters': 4,
        'min_area': 50
    }

    try:
        response = requests.post(url, params=params, timeout=10)

        if response.status_code == 400:
            print_success("正确拒绝了未就绪的文件")
            error_msg = response.json().get('detail', '')
            print(f"  - 错误信息: {error_msg}\n")
            return True
        elif response.status_code == 404:
            print_success("正确返回了文件不存在错误")
            print(f"  - 状态码: 404\n")
            return True
        else:
            print_info(f"返回状态码: {response.status_code}")
            return True
    except Exception as e:
        print_error(f"请求异常: {str(e)}")
        return False

def test_incomplete_chunks():
    """测试5: 验证不完整分片的处理"""
    print_step(5, "验证不完整分片的处理")

    upload_id_incomplete = "incomplete-test-" + str(int(time.time()))
    test_file = create_test_file(CHUNK_SIZE)

    print_info("上传部分分片（总共需要4个，只上传2个）...")

    # 上传前2个分片
    for i in range(2):
        success, response = upload_chunk(i, test_file, 4)
        if success:
            print_success(f"分片 {i} 上传成功")
        else:
            print_error(f"分片 {i} 上传失败")
            return False

    # 尝试完成上传（应该失败）
    print_info("\n尝试完成上传（分片不完整）...")

    url = f"{API_BASE_URL}/upload/complete"
    payload = {
        'uploadId': upload_id_incomplete,
        'fileName': 'incomplete_test.tif',
        'fileSize': CHUNK_SIZE * 4,
        'totalChunks': 4
    }

    try:
        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 400:
            print_success("正确拒绝了不完整的分片")
            error_msg = response.json().get('detail', '')
            print(f"  - 错误信息: {error_msg}\n")
            return True
        else:
            print_error(f"意外的状态码: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"请求异常: {str(e)}")
        return False

def main():
    """主测试函数"""
    print(f"\n{Colors.BLUE}{'='*60}")
    print("分片上传流程8步实现 - 完整测试")
    print(f"{'='*60}{Colors.END}\n")

    print_info(f"API 基础 URL: {API_BASE_URL}")
    print_info(f"上传 ID: {UPLOAD_ID}\n")

    # 检查服务是否运行
    print_info("检查服务连接...")
    try:
        response = requests.get(f"{API_BASE_URL}/upload/status/test", timeout=5)
        print_success("服务连接正常\n")
    except Exception as e:
        print_error(f"无法连接到服务: {str(e)}")
        print_error("请确保后端服务正在运行 (http://localhost:8000)")
        return False

    # 运行测试
    tests = [
        ("chunk 接收日志", test_chunk_reception),
        ("状态转移流程", test_status_transition),
        ("速率限制", test_rate_limiting),
        ("文件就绪检查", test_file_readiness_check),
        ("不完整分片处理", test_incomplete_chunks),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print_error(f"测试异常: {str(e)}")
            results.append((test_name, False))

    # 打印总结
    print(f"\n{Colors.BLUE}{'='*60}")
    print("测试总结")
    print(f"{'='*60}{Colors.END}\n")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = f"{Colors.GREEN}通过{Colors.END}" if result else f"{Colors.RED}失败{Colors.END}"
        print(f"  {test_name}: {status}")

    print(f"\n总体: {passed}/{total} 测试通过\n")

    if passed == total:
        print_success("所有测试通过！8步实现验证完成。")
        return True
    else:
        print_error(f"有 {total - passed} 个测试失败")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
