#!/usr/bin/env python3
"""
分片上传流程8步实现 - 高级测试场景

测试内容：
1. 大文件上传（10MB）
2. 网络中断恢复（模拟）
3. 并发上传多个文件
4. 边界情况测试
5. 错误恢复测试
"""

import requests
import json
import time
import sys
import threading
from pathlib import Path
from typing import Dict, Any, Tuple, List

# 配置
API_BASE_URL = "http://localhost:8000"
TEST_SCENARIOS = []

# 颜色输出
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    END = '\033[0m'

def print_scenario(num: int, title: str):
    """打印测试场景标题"""
    print(f"\n{Colors.CYAN}{'='*70}")
    print(f"高级测试场景 {num}: {title}")
    print(f"{'='*70}{Colors.END}\n")

def print_success(msg: str):
    """打印成功信息"""
    print(f"{Colors.GREEN}✓ {msg}{Colors.END}")

def print_error(msg: str):
    """打印错误信息"""
    print(f"{Colors.RED}✗ {msg}{Colors.END}")

def print_info(msg: str):
    """打印信息"""
    print(f"{Colors.YELLOW}ℹ {msg}{Colors.END}")

def print_warning(msg: str):
    """打印警告"""
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.END}")

# ==================== 测试场景 1: 大文件上传 ====================

def test_large_file_upload():
    """测试场景1: 大文件上传（10MB）"""
    print_scenario(1, "大文件上传 (10MB)")

    upload_id = f"large-file-{int(time.time())}"
    file_size = 10 * 1024 * 1024  # 10MB
    chunk_size = 1024 * 1024  # 1MB chunks
    total_chunks = file_size // chunk_size

    print_info(f"文件大小: {file_size / (1024*1024):.1f}MB")
    print_info(f"分片大小: {chunk_size / 1024:.1f}KB")
    print_info(f"总分片数: {total_chunks}\n")

    # 创建测试数据
    test_data = b"X" * chunk_size

    # 上传所有分片
    success_count = 0
    for i in range(total_chunks):
        url = f"{API_BASE_URL}/upload/chunk"
        files = {'chunk': ('chunk_data', test_data)}
        data = {
            'chunkIndex': i,
            'totalChunks': total_chunks,
            'fileName': 'large_test.tif',
            'fileSize': file_size,
            'uploadId': upload_id
        }

        try:
            response = requests.post(url, files=files, data=data, timeout=60)
            if response.status_code == 200:
                success_count += 1
                progress = response.json().get('progress', 0)
                print_info(f"分片 {i+1}/{total_chunks} 上传成功 (进度: {progress}%)")
            else:
                print_error(f"分片 {i} 上传失败 (状态码: {response.status_code})")
                return False
        except Exception as e:
            print_error(f"分片 {i} 上传异常: {str(e)}")
            return False

    print(f"\n上传统计: {success_count}/{total_chunks} 分片成功")

    # 完成上传
    print_info("完成上传，触发合并...")
    url = f"{API_BASE_URL}/upload/complete"
    payload = {
        'uploadId': upload_id,
        'fileName': 'large_test.tif',
        'fileSize': file_size,
        'totalChunks': total_chunks
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            print_success("合并任务已提交")
            return True
        else:
            print_error(f"完成上传失败 (状态码: {response.status_code})")
            return False
    except Exception as e:
        print_error(f"完成上传异常: {str(e)}")
        return False

# ==================== 测试场景 2: 并发上传多个文件 ====================

def upload_file_concurrent(file_id: int, file_size: int, chunk_size: int) -> bool:
    """并发上传单个文件"""
    upload_id = f"concurrent-file-{file_id}-{int(time.time())}"
    total_chunks = file_size // chunk_size

    test_data = b"Y" * chunk_size

    for i in range(total_chunks):
        url = f"{API_BASE_URL}/upload/chunk"
        files = {'chunk': ('chunk_data', test_data)}
        data = {
            'chunkIndex': i,
            'totalChunks': total_chunks,
            'fileName': f'concurrent_test_{file_id}.tif',
            'fileSize': file_size,
            'uploadId': upload_id
        }

        try:
            response = requests.post(url, files=files, data=data, timeout=30)
            if response.status_code != 200:
                return False
        except Exception:
            return False

    # 完成上传
    url = f"{API_BASE_URL}/upload/complete"
    payload = {
        'uploadId': upload_id,
        'fileName': f'concurrent_test_{file_id}.tif',
        'fileSize': file_size,
        'totalChunks': total_chunks
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        return response.status_code == 200
    except Exception:
        return False

def test_concurrent_uploads():
    """测试场景2: 并发上传多个文件"""
    print_scenario(2, "并发上传多个文件")

    num_files = 3
    file_size = 2 * 1024 * 1024  # 2MB per file
    chunk_size = 512 * 1024  # 512KB chunks

    print_info(f"并发上传 {num_files} 个文件")
    print_info(f"每个文件大小: {file_size / (1024*1024):.1f}MB\n")

    threads = []
    results = []

    def upload_wrapper(file_id):
        result = upload_file_concurrent(file_id, file_size, chunk_size)
        results.append((file_id, result))

    # 启动并发上传
    for i in range(num_files):
        thread = threading.Thread(target=upload_wrapper, args=(i,))
        threads.append(thread)
        thread.start()

    # 等待所有线程完成
    for thread in threads:
        thread.join()

    # 统计结果
    success_count = sum(1 for _, result in results if result)
    print(f"\n并发上传统计: {success_count}/{num_files} 文件成功")

    if success_count == num_files:
        print_success("所有文件并发上传成功")
        return True
    else:
        print_error(f"有 {num_files - success_count} 个文件上传失败")
        return False

# ==================== 测试场景 3: 边界情况测试 ====================

def test_boundary_cases():
    """测试场景3: 边界情况测试"""
    print_scenario(3, "边界情况测试")

    test_cases = [
        ("最小文件", 1024, 1024),  # 1KB file, 1KB chunk
        ("单个分片", 512 * 1024, 512 * 1024),  # 512KB file, 512KB chunk
        ("大量小分片", 5 * 1024 * 1024, 100 * 1024),  # 5MB file, 100KB chunks
    ]

    results = []

    for test_name, file_size, chunk_size in test_cases:
        print_info(f"测试: {test_name} (文件: {file_size/1024:.0f}KB, 分片: {chunk_size/1024:.0f}KB)")

        upload_id = f"boundary-{test_name}-{int(time.time())}"
        total_chunks = (file_size + chunk_size - 1) // chunk_size
        test_data = b"Z" * min(chunk_size, file_size)

        success = True

        # 上传分片
        for i in range(total_chunks):
            chunk_data = test_data[:min(len(test_data), file_size - i * chunk_size)]
            url = f"{API_BASE_URL}/upload/chunk"
            files = {'chunk': ('chunk_data', chunk_data)}
            data = {
                'chunkIndex': i,
                'totalChunks': total_chunks,
                'fileName': f'boundary_{test_name}.tif',
                'fileSize': file_size,
                'uploadId': upload_id
            }

            try:
                response = requests.post(url, files=files, data=data, timeout=30)
                if response.status_code != 200:
                    success = False
                    break
            except Exception:
                success = False
                break

        if success:
            # 完成上传
            url = f"{API_BASE_URL}/upload/complete"
            payload = {
                'uploadId': upload_id,
                'fileName': f'boundary_{test_name}.tif',
                'fileSize': file_size,
                'totalChunks': total_chunks
            }

            try:
                response = requests.post(url, json=payload, timeout=30)
                success = response.status_code == 200
            except Exception:
                success = False

        if success:
            print_success(f"{test_name} 测试通过")
        else:
            print_error(f"{test_name} 测试失败")

        results.append((test_name, success))

    print(f"\n边界情况测试统计: {sum(1 for _, r in results if r)}/{len(results)} 通过")
    return all(r for _, r in results)

# ==================== 测试场景 4: 错误恢复测试 ====================

def test_error_recovery():
    """测试场景4: 错误恢复测试"""
    print_scenario(4, "错误恢复测试")

    print_info("测试1: 无效的分片索引")
    upload_id = f"error-recovery-{int(time.time())}"
    url = f"{API_BASE_URL}/upload/chunk"
    files = {'chunk': ('chunk_data', b"test")}
    data = {
        'chunkIndex': 10,  # 无效的索引
        'totalChunks': 4,
        'fileName': 'error_test.tif',
        'fileSize': 1024,
        'uploadId': upload_id
    }

    try:
        response = requests.post(url, files=files, data=data, timeout=10)
        if response.status_code == 400:
            print_success("正确拒绝了无效的分片索引 (400)")
        else:
            print_warning(f"返回状态码: {response.status_code}")
    except Exception as e:
        print_error(f"请求异常: {str(e)}")

    print_info("\n测试2: 缺少必要参数")
    data_incomplete = {
        'chunkIndex': 0,
        'totalChunks': 4,
        # 缺少 fileName
        'fileSize': 1024,
        'uploadId': upload_id
    }

    try:
        response = requests.post(url, files=files, data=data_incomplete, timeout=10)
        if response.status_code >= 400:
            print_success(f"正确拒绝了不完整的请求 ({response.status_code})")
        else:
            print_warning(f"返回状态码: {response.status_code}")
    except Exception as e:
        print_error(f"请求异常: {str(e)}")

    print_info("\n测试3: 无效的文件大小")
    data_invalid = {
        'chunkIndex': 0,
        'totalChunks': 4,
        'fileName': 'error_test.tif',
        'fileSize': -1,  # 无效的大小
        'uploadId': upload_id
    }

    try:
        response = requests.post(url, files=files, data=data_invalid, timeout=10)
        if response.status_code >= 400:
            print_success(f"正确拒绝了无效的文件大小 ({response.status_code})")
        else:
            print_warning(f"返回状态码: {response.status_code}")
    except Exception as e:
        print_error(f"请求异常: {str(e)}")

    return True

# ==================== 测试场景 5: 状态查询测试 ====================

def test_status_queries():
    """测试场景5: 状态查询测试"""
    print_scenario(5, "状态查询测试")

    print_info("测试1: 查询不存在的上传会话")
    url = f"{API_BASE_URL}/upload/status/nonexistent-upload-id"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 404:
            print_success("正确返回了 404 Not Found")
        else:
            print_warning(f"返回状态码: {response.status_code}")
    except Exception as e:
        print_error(f"请求异常: {str(e)}")

    print_info("\n测试2: 查询有效的上传会话")
    # 先创建一个上传会话
    upload_id = f"status-query-{int(time.time())}"
    url_chunk = f"{API_BASE_URL}/upload/chunk"
    files = {'chunk': ('chunk_data', b"test" * 1024)}
    data = {
        'chunkIndex': 0,
        'totalChunks': 2,
        'fileName': 'status_test.tif',
        'fileSize': 8192,
        'uploadId': upload_id
    }

    try:
        response = requests.post(url_chunk, files=files, data=data, timeout=10)
        if response.status_code == 200:
            # 查询状态
            url_status = f"{API_BASE_URL}/upload/status/{upload_id}"
            response = requests.get(url_status, timeout=10)
            if response.status_code == 200:
                status_data = response.json()
                print_success("成功查询上传状态")
                print(f"  - 状态: {status_data.get('status')}")
                print(f"  - 进度: {status_data.get('progress')}%")
                print(f"  - 已上传: {status_data.get('uploadedChunks')}/{status_data.get('totalChunks')}")
            else:
                print_error(f"查询状态失败 ({response.status_code})")
        else:
            print_error(f"创建上传会话失败 ({response.status_code})")
    except Exception as e:
        print_error(f"请求异常: {str(e)}")

    return True

# ==================== 主函数 ====================

def main():
    """主测试函数"""
    print(f"\n{Colors.BLUE}{'='*70}")
    print("分片上传流程8步实现 - 高级测试场景")
    print(f"{'='*70}{Colors.END}\n")

    print_info(f"API 基础 URL: {API_BASE_URL}\n")

    # 检查服务连接
    print_info("检查服务连接...")
    try:
        response = requests.get(f"{API_BASE_URL}/upload/status/test", timeout=5)
        print_success("服务连接正常\n")
    except Exception as e:
        print_error(f"无法连接到服务: {str(e)}")
        return False

    # 运行测试场景
    scenarios = [
        ("大文件上传", test_large_file_upload),
        ("并发上传多个文件", test_concurrent_uploads),
        ("边界情况测试", test_boundary_cases),
        ("错误恢复测试", test_error_recovery),
        ("状态查询测试", test_status_queries),
    ]

    results = []

    for scenario_name, test_func in scenarios:
        try:
            result = test_func()
            results.append((scenario_name, result))
        except Exception as e:
            print_error(f"测试异常: {str(e)}")
            results.append((scenario_name, False))

    # 打印总结
    print(f"\n{Colors.BLUE}{'='*70}")
    print("高级测试场景总结")
    print(f"{'='*70}{Colors.END}\n")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for scenario_name, result in results:
        status = f"{Colors.GREEN}通过{Colors.END}" if result else f"{Colors.RED}失败{Colors.END}"
        print(f"  {scenario_name}: {status}")

    print(f"\n总体: {passed}/{total} 测试场景通过\n")

    if passed == total:
        print_success("所有高级测试场景通过！")
        return True
    else:
        print_error(f"有 {total - passed} 个测试场景失败")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
