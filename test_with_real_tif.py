#!/usr/bin/env python3
"""
使用真实TIFF文件进行完整项目测试
测试文件: /Users/wuchenkai/解译程序/20201023.tif (4.0GB)

测试流程:
1. 验证后端服务是否运行
2. 测试文件上传功能
3. 测试文件合并功能
4. 测试检测功能
5. 验证结果
"""

import requests
import json
import time
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# 配置
BACKEND_URL = "http://localhost:8000"
TEST_FILE = Path("/Users/wuchenkai/解译程序/20201023.tif")  # 使用真实的TIFF文件
CHUNK_SIZE = 5 * 1024 * 1024  # 5MB
MAX_RETRIES = 3
RETRY_DELAY = 2

# 颜色定义
class Colors:
    BLUE = '\033[0;34m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'

def log_info(msg: str):
    print(f"{Colors.BLUE}[INFO]{Colors.NC} {msg}")

def log_success(msg: str):
    print(f"{Colors.GREEN}[SUCCESS]{Colors.NC} {msg}")

def log_warning(msg: str):
    print(f"{Colors.YELLOW}[WARNING]{Colors.NC} {msg}")

def log_error(msg: str):
    print(f"{Colors.RED}[ERROR]{Colors.NC} {msg}")

def log_debug(msg: str):
    print(f"{Colors.CYAN}[DEBUG]{Colors.NC} {msg}")

def check_backend_health() -> bool:
    """检查后端服务是否运行"""
    log_info("检查后端服务健康状态...")
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        if response.status_code == 200:
            log_success("后端服务运行正常")
            return True
        else:
            log_error(f"后端服务返回异常状态码: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        log_error(f"无法连接到后端服务 ({BACKEND_URL})")
        log_error("请确保后端服务已启动: ./start.sh")
        return False
    except Exception as e:
        log_error(f"检查后端服务失败: {str(e)}")
        return False

def verify_test_file() -> bool:
    """验证测试文件是否存在"""
    log_info(f"验证测试文件: {TEST_FILE}")
    if not TEST_FILE.exists():
        log_error(f"测试文件不存在: {TEST_FILE}")
        return False

    file_size = TEST_FILE.stat().st_size
    log_success(f"测试文件存在，大小: {file_size / (1024**3):.2f}GB")
    return True

def upload_file_chunks(file_path: Path) -> Optional[Dict[str, Any]]:
    """分片上传文件"""
    log_info(f"开始上传文件: {file_path.name}")

    file_size = file_path.stat().st_size
    total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
    upload_id = f"test-{int(time.time())}"

    log_info(f"文件大小: {file_size / (1024**3):.2f}GB")
    log_info(f"总分片数: {total_chunks}")
    log_info(f"上传ID: {upload_id}")

    uploaded_chunks = []

    try:
        with open(file_path, 'rb') as f:
            for chunk_index in range(total_chunks):
                chunk_data = f.read(CHUNK_SIZE)
                if not chunk_data:
                    break

                # 上传分片
                files = {'chunk': chunk_data}
                data = {
                    'uploadId': upload_id,
                    'chunkIndex': chunk_index,
                    'totalChunks': total_chunks,
                    'fileName': file_path.name,
                    'fileSize': file_size,
                }

                # 重试逻辑
                retry_count = 0
                while retry_count < MAX_RETRIES:
                    try:
                        response = requests.post(
                            f"{BACKEND_URL}/api/upload/chunk",
                            files=files,
                            data=data,
                            timeout=60
                        )

                        if response.status_code == 200:
                            uploaded_chunks.append(chunk_index)
                            progress = (chunk_index + 1) / total_chunks * 100
                            log_debug(f"分片 {chunk_index + 1}/{total_chunks} 上传成功 ({progress:.1f}%)")
                            # 添加小延迟以避免触发速率限制
                            time.sleep(0.05)
                            break
                        elif response.status_code == 429:
                            # 速率限制，等待后重试
                            retry_count += 1
                            if retry_count < MAX_RETRIES:
                                wait_time = RETRY_DELAY * retry_count
                                log_warning(f"分片 {chunk_index} 触发速率限制，{wait_time}秒后重试...")
                                time.sleep(wait_time)
                            else:
                                log_error(f"分片 {chunk_index} 上传失败: {response.status_code}")
                                log_error(f"响应: {response.text}")
                                return None
                        else:
                            log_error(f"分片 {chunk_index} 上传失败: {response.status_code}")
                            log_error(f"响应: {response.text}")
                            return None

                    except requests.exceptions.Timeout:
                        retry_count += 1
                        if retry_count < MAX_RETRIES:
                            log_warning(f"分片 {chunk_index} 上传超时，{RETRY_DELAY}秒后重试...")
                            time.sleep(RETRY_DELAY)
                        else:
                            log_error(f"分片 {chunk_index} 上传超时")
                            return None
                    except Exception as e:
                        log_error(f"分片 {chunk_index} 上传异常: {str(e)}")
                        return None

        log_success(f"所有分片上传完成 ({len(uploaded_chunks)}/{total_chunks})")

        # 完成上传
        log_info("完成上传...")
        complete_response = requests.post(
            f"{BACKEND_URL}/api/upload/complete",
            json={
                'uploadId': upload_id,
                'fileName': file_path.name,
                'fileSize': file_size,
                'totalChunks': total_chunks,
            },
            timeout=30
        )

        if complete_response.status_code == 200:
            result = complete_response.json()
            log_success("上传完成请求已提交")
            log_debug(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return {
                'uploadId': upload_id,
                'fileName': file_path.name,
                'fileSize': file_size,
                'totalChunks': total_chunks,
                'taskId': result.get('taskId'),
            }
        else:
            log_error(f"完成上传失败: {complete_response.status_code}")
            log_error(f"响应: {complete_response.text}")
            return None

    except Exception as e:
        log_error(f"上传过程异常: {str(e)}")
        return None

def wait_for_merge(upload_id: str, max_wait: int = 300) -> Optional[str]:
    """等待文件合并完成"""
    log_info(f"等待文件合并完成 (最多等待 {max_wait}秒)...")

    start_time = time.time()
    check_interval = 5

    while time.time() - start_time < max_wait:
        try:
            response = requests.get(
                f"{BACKEND_URL}/api/upload/status/{upload_id}",
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                status = data.get('status')
                progress = data.get('progress', 0)

                log_debug(f"状态: {status}, 进度: {progress}%")

                if status == 'completed':
                    file_path = data.get('filePath')
                    log_success(f"文件合并完成: {file_path}")
                    return file_path
                elif status == 'failed':
                    error_msg = data.get('errorMessage', '未知错误')
                    log_error(f"文件合并失败: {error_msg}")
                    return None
            else:
                log_warning(f"查询状态失败: {response.status_code}")

        except Exception as e:
            log_warning(f"查询状态异常: {str(e)}")

        time.sleep(check_interval)

    log_error(f"等待超时 ({max_wait}秒)")
    return None

def test_detection(file_path: str) -> Optional[str]:
    """测试检测功能"""
    log_info(f"启动检测任务: {file_path}")

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/unsupervised/detect",
            params={
                'image_path': file_path,
                'n_clusters': 4,
                'min_area': 50,
            },
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            task_id = result.get('task_id')
            log_success(f"检测任务已启动: {task_id}")
            log_debug(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return task_id
        else:
            log_error(f"启动检测失败: {response.status_code}")
            log_error(f"响应: {response.text}")
            return None

    except Exception as e:
        log_error(f"启动检测异常: {str(e)}")
        return None

def wait_for_detection(task_id: str, max_wait: int = 600) -> bool:
    """等待检测完成"""
    log_info(f"等待检测完成 (最多等待 {max_wait}秒)...")

    start_time = time.time()
    check_interval = 10

    while time.time() - start_time < max_wait:
        try:
            response = requests.get(
                f"{BACKEND_URL}/api/unsupervised/task-status/{task_id}",
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                status = data.get('status')
                progress = data.get('progress', 0)
                stage = data.get('current_stage', '未知')

                log_debug(f"状态: {status}, 进度: {progress}%, 阶段: {stage}")

                if status == 'completed':
                    log_success("检测完成")
                    log_debug(f"结果: {json.dumps(data.get('result', {}), indent=2, ensure_ascii=False)}")
                    return True
                elif status == 'failed':
                    error_msg = data.get('error', '未知错误')
                    log_error(f"检测失败: {error_msg}")
                    return False
            else:
                log_warning(f"查询状态失败: {response.status_code}")

        except Exception as e:
            log_warning(f"查询状态异常: {str(e)}")

        time.sleep(check_interval)

    log_error(f"等待超时 ({max_wait}秒)")
    return False

def main():
    """主测试流程"""
    print()
    print(f"{Colors.BLUE}╔════════════════════════════════════════════════════════╗{Colors.NC}")
    print(f"{Colors.BLUE}║{Colors.NC}     使用真实TIFF文件进行完整项目测试                 {Colors.BLUE}║{Colors.NC}")
    print(f"{Colors.BLUE}╚════════════════════════════════════════════════════════╝{Colors.NC}")
    print()

    # 步骤1: 检查后端服务
    log_info("步骤1: 检查后端服务")
    if not check_backend_health():
        log_error("后端服务检查失败，无法继续测试")
        return False
    print()

    # 步骤2: 验证测试文件
    log_info("步骤2: 验证测试文件")
    if not verify_test_file():
        log_error("测试文件验证失败")
        return False
    print()

    # 步骤3: 上传文件
    log_info("步骤3: 上传文件")
    upload_result = upload_file_chunks(TEST_FILE)
    if not upload_result:
        log_error("文件上传失败")
        return False
    print()

    # 步骤4: 等待文件合并
    log_info("步骤4: 等待文件合并")
    merged_file_path = wait_for_merge(upload_result['uploadId'], max_wait=600)
    if not merged_file_path:
        log_error("文件合并失败或超时")
        return False
    print()

    # 步骤5: 测试检测功能
    log_info("步骤5: 启动检测任务")
    task_id = test_detection(merged_file_path)
    if not task_id:
        log_error("检测任务启动失败")
        return False
    print()

    # 步骤6: 等待检测完成
    log_info("步骤6: 等待检测完成")
    if not wait_for_detection(task_id, max_wait=600):
        log_error("检测失败或超时")
        return False
    print()

    # 测试完成
    print(f"{Colors.BLUE}╔════════════════════════════════════════════════════════╗{Colors.NC}")
    print(f"{Colors.GREEN}║{Colors.NC}  ✅ 完整项目测试成功！                              {Colors.BLUE}║{Colors.NC}")
    print(f"{Colors.BLUE}╚════════════════════════════════════════════════════════╝{Colors.NC}")
    print()

    return True

if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print()
        log_warning("测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print()
        log_error(f"测试异常: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
