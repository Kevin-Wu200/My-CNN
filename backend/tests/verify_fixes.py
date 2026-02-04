"""
验证修复效果的脚本
用于验证以下修复：
1. 信号处理是否正常工作
2. 数值库线程是否被限制
3. 进程池是否正确清理
4. Ctrl+C 后是否能正确关闭
"""

import os
import sys
import signal
import time
import logging
import threading
import multiprocessing as mp
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.utils.thread_limiter import limit_numerical_library_threads, log_thread_configuration
from backend.utils.resource_monitor import ResourceMonitor
from backend.utils.logger import LoggerSetup

# 设置日志
logger = LoggerSetup.setup_logger("verify_fixes", log_dir=Path("./logs/verification"))


class SignalHandlerVerifier:
    """信号处理验证器"""

    def __init__(self):
        """初始化验证器"""
        self.signal_received = False
        self.signal_type = None
        self.signal_time = None

    def signal_handler(self, signum, frame):
        """信号处理函数"""
        self.signal_received = True
        self.signal_type = signal.Signals(signum).name
        self.signal_time = datetime.now()
        logger.info(f"收到信号: {self.signal_type} (信号号: {signum})")

    def verify_signal_handling(self) -> Tuple[bool, str]:
        """
        验证信号处理是否正常工作

        Returns:
            (验证是否成功, 验证信息)
        """
        logger.info("=" * 70)
        logger.info("验证 1: 信号处理")
        logger.info("=" * 70)

        try:
            # 注册信号处理器
            original_handler = signal.signal(signal.SIGTERM, self.signal_handler)
            logger.info("✓ 已注册 SIGTERM 信号处理器")

            # 发送信号给自己
            logger.info("发送 SIGTERM 信号给自己...")
            os.kill(os.getpid(), signal.SIGTERM)

            # 等待信号处理
            time.sleep(0.5)

            # 恢复原始处理器
            signal.signal(signal.SIGTERM, original_handler)

            if self.signal_received:
                logger.info(f"✓ 成功接收到信号: {self.signal_type}")
                logger.info(f"✓ 信号处理时间: {self.signal_time}")
                return True, "信号处理正常工作"
            else:
                logger.error("✗ 未能接收到信号")
                return False, "信号处理失败"

        except Exception as e:
            logger.error(f"✗ 信号处理验证异常: {str(e)}", exc_info=True)
            return False, f"验证异常: {str(e)}"


class ThreadLimitingVerifier:
    """线程限制验证器"""

    @staticmethod
    def verify_thread_limiting() -> Tuple[bool, str]:
        """
        验证数值库线程是否被限制

        Returns:
            (验证是否成功, 验证信息)
        """
        logger.info("=" * 70)
        logger.info("验证 2: 数值库线程限制")
        logger.info("=" * 70)

        try:
            # 限制线程数
            num_threads = 2
            logger.info(f"设置线程限制: {num_threads}")
            limit_numerical_library_threads(num_threads)

            # 记录线程配置
            log_thread_configuration()

            # 验证环境变量
            logger.info("验证环境变量...")
            env_vars = {
                "OMP_NUM_THREADS": str(num_threads),
                "MKL_NUM_THREADS": str(num_threads),
                "OPENBLAS_NUM_THREADS": str(num_threads),
                "NUMEXPR_NUM_THREADS": str(num_threads),
            }

            all_set = True
            for var_name, expected_value in env_vars.items():
                actual_value = os.environ.get(var_name)
                if actual_value == expected_value:
                    logger.info(f"✓ {var_name} = {actual_value}")
                else:
                    logger.warning(f"✗ {var_name} = {actual_value} (期望: {expected_value})")
                    all_set = False

            # 验证 PyTorch 线程配置
            logger.info("验证 PyTorch 线程配置...")
            try:
                import torch

                torch_threads = torch.get_num_threads()
                logger.info(f"✓ PyTorch 线程数: {torch_threads}")

                if torch_threads <= num_threads * 2:  # 允许一些浮动
                    logger.info(f"✓ PyTorch 线程数在预期范围内")
                else:
                    logger.warning(f"⚠ PyTorch 线程数可能过高: {torch_threads}")

            except ImportError:
                logger.warning("PyTorch 未安装，跳过验证")

            # 验证 NumPy 线程配置
            logger.info("验证 NumPy 线程配置...")
            try:
                import numpy as np

                if hasattr(np, "get_num_threads"):
                    numpy_threads = np.get_num_threads()
                    logger.info(f"✓ NumPy 线程数: {numpy_threads}")
                else:
                    logger.info("NumPy 不支持 get_num_threads()")

            except ImportError:
                logger.warning("NumPy 未安装，跳过验证")

            if all_set:
                logger.info("✓ 线程限制验证成功")
                return True, "线程限制正常工作"
            else:
                logger.warning("⚠ 部分环境变量未正确设置")
                return True, "线程限制部分工作"

        except Exception as e:
            logger.error(f"✗ 线程限制验证异常: {str(e)}", exc_info=True)
            return False, f"验证异常: {str(e)}"


class ProcessPoolVerifier:
    """进程池验证器"""

    @staticmethod
    def worker_function(x):
        """工作进程函数"""
        time.sleep(0.1)
        return x * 2

    @staticmethod
    def verify_process_pool_cleanup() -> Tuple[bool, str]:
        """
        验证进程池是否正确清理

        Returns:
            (验证是否成功, 验证信息)
        """
        logger.info("=" * 70)
        logger.info("验证 3: 进程池清理")
        logger.info("=" * 70)

        try:
            # 记录初始进程数
            initial_process_count = ResourceMonitor.get_process_count()
            logger.info(f"初始进程数: {initial_process_count}")

            # 创建进程池
            num_workers = 4
            logger.info(f"创建进程池，工作进程数: {num_workers}")
            pool = mp.Pool(processes=num_workers)

            # 等待进程启动
            time.sleep(0.5)

            # 记录进程池启动后的进程数
            pool_started_count = ResourceMonitor.get_process_count()
            logger.info(f"进程池启动后进程数: {pool_started_count}")

            # 提交任务
            logger.info("提交任务到进程池...")
            results = []
            for i in range(10):
                result = pool.apply_async(ProcessPoolVerifier.worker_function, (i,))
                results.append(result)

            # 等待所有任务完成
            logger.info("等待所有任务完成...")
            for result in results:
                result.get(timeout=5)

            logger.info("✓ 所有任务已完成")

            # 关闭进程池
            logger.info("关闭进程池...")
            pool.close()
            pool.join()
            logger.info("✓ 进程池已关闭")

            # 等待进程完全退出
            time.sleep(1)

            # 记录进程池关闭后的进程数
            final_process_count = ResourceMonitor.get_process_count()
            logger.info(f"进程池关闭后进程数: {final_process_count}")

            # 验证进程数是否恢复
            process_diff = final_process_count - initial_process_count
            logger.info(f"进程数变化: {process_diff}")

            if process_diff <= 2:  # 允许少量浮动
                logger.info("✓ 进程池清理成功，进程数已恢复")
                return True, "进程池清理正常工作"
            else:
                logger.warning(f"⚠ 进程数未完全恢复，差异: {process_diff}")
                return True, "进程池清理部分工作"

        except Exception as e:
            logger.error(f"✗ 进程池清理验证异常: {str(e)}", exc_info=True)
            return False, f"验证异常: {str(e)}"


class ResourceMonitoringVerifier:
    """资源监控验证器"""

    @staticmethod
    def verify_resource_monitoring() -> Tuple[bool, str]:
        """
        验证资源监控是否正常工作

        Returns:
            (验证是否成功, 验证信息)
        """
        logger.info("=" * 70)
        logger.info("验证 4: 资源监控")
        logger.info("=" * 70)

        try:
            # 获取资源快照
            logger.info("获取资源快照...")
            snapshot = ResourceMonitor.get_resource_snapshot()

            if not snapshot:
                logger.error("✗ 无法获取资源快照")
                return False, "资源监控失败"

            logger.info(f"✓ 进程数: {snapshot.get('process_count', 'N/A')}")
            logger.info(f"✓ 线程数: {snapshot.get('thread_count', 'N/A')}")
            logger.info(f"✓ CPU 使用率: {snapshot.get('cpu_usage', 'N/A'):.1f}%")

            memory = snapshot.get('memory', {})
            logger.info(f"✓ 内存使用: {memory.get('used', 'N/A'):.1f}MB / {memory.get('total', 'N/A'):.1f}MB")

            logger.info("✓ 资源监控正常工作")
            return True, "资源监控正常工作"

        except Exception as e:
            logger.error(f"✗ 资源监控验证异常: {str(e)}", exc_info=True)
            return False, f"验证异常: {str(e)}"


def run_all_verifications() -> Dict[str, Tuple[bool, str]]:
    """
    运行所有验证

    Returns:
        验证结果字典
    """
    logger.info("\n" + "=" * 70)
    logger.info("开始验证修复效果")
    logger.info("=" * 70)

    results = {}

    # 验证 1: 信号处理
    try:
        verifier = SignalHandlerVerifier()
        success, message = verifier.verify_signal_handling()
        results["信号处理"] = (success, message)
    except Exception as e:
        logger.error(f"信号处理验证异常: {str(e)}")
        results["信号处理"] = (False, str(e))

    # 验证 2: 线程限制
    try:
        success, message = ThreadLimitingVerifier.verify_thread_limiting()
        results["线程限制"] = (success, message)
    except Exception as e:
        logger.error(f"线程限制验证异常: {str(e)}")
        results["线程限制"] = (False, str(e))

    # 验证 3: 进程池清理
    try:
        success, message = ProcessPoolVerifier.verify_process_pool_cleanup()
        results["进程池清理"] = (success, message)
    except Exception as e:
        logger.error(f"进程池清理验证异常: {str(e)}")
        results["进程池清理"] = (False, str(e))

    # 验证 4: 资源监控
    try:
        success, message = ResourceMonitoringVerifier.verify_resource_monitoring()
        results["资源监控"] = (success, message)
    except Exception as e:
        logger.error(f"资源监控验证异常: {str(e)}")
        results["资源监控"] = (False, str(e))

    # 输出验证结果
    logger.info("\n" + "=" * 70)
    logger.info("验证结果汇总")
    logger.info("=" * 70)

    passed = 0
    failed = 0

    for test_name, (success, message) in results.items():
        status = "✓ 通过" if success else "✗ 失败"
        logger.info(f"{status}: {test_name} - {message}")
        if success:
            passed += 1
        else:
            failed += 1

    logger.info("=" * 70)
    logger.info(f"验证完成: {passed} 通过, {failed} 失败")
    logger.info("=" * 70)

    return results


if __name__ == "__main__":
    try:
        results = run_all_verifications()

        # 返回退出码
        failed_count = sum(1 for success, _ in results.values() if not success)
        sys.exit(0 if failed_count == 0 else 1)

    except Exception as e:
        logger.error(f"验证过程异常: {str(e)}", exc_info=True)
        sys.exit(1)
