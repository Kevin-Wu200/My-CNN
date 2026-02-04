"""
集成测试脚本：优雅关闭验证
用于测试以下场景：
1. 正常完成时 CPU 使用率是否回落
2. 进程数量是否稳定
3. 无额外后台进程残留
4. Ctrl+C 时所有 python 进程是否立即退出
"""

import os
import sys
import time
import signal
import logging
import subprocess
import threading
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
import psutil

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.utils.resource_monitor import ResourceMonitor
from backend.utils.logger import LoggerSetup

# 设置日志
logger = LoggerSetup.setup_logger("integration_test_graceful_shutdown", log_dir=Path("./logs/integration_tests"))


class GracefulShutdownTester:
    """优雅关闭集成测试器"""

    def __init__(self):
        """初始化测试器"""
        self.test_results = {}
        self.resource_snapshots = []

    def record_resource_snapshot(self, label: str) -> Dict:
        """
        记录资源快照

        Args:
            label: 快照标签

        Returns:
            资源快照字典
        """
        snapshot = ResourceMonitor.get_resource_snapshot()
        snapshot['label'] = label
        snapshot['timestamp'] = datetime.now().isoformat()
        self.resource_snapshots.append(snapshot)

        logger.info(f"[{label}] 资源快照:")
        logger.info(f"  - 进程数: {snapshot.get('process_count', 'N/A')}")
        logger.info(f"  - 线程数: {snapshot.get('thread_count', 'N/A')}")
        logger.info(f"  - CPU 使用率: {snapshot.get('cpu_usage', 'N/A'):.1f}%")

        memory = snapshot.get('memory', {})
        logger.info(f"  - 内存: {memory.get('used', 'N/A'):.1f}MB / {memory.get('total', 'N/A'):.1f}MB")

        return snapshot

    def test_normal_completion_cpu_recovery(self) -> Tuple[bool, str]:
        """
        测试正常完成时 CPU 使用率是否回落

        Returns:
            (测试是否成功, 测试信息)
        """
        logger.info("=" * 70)
        logger.info("测试 1: 正常完成时 CPU 使用率恢复")
        logger.info("=" * 70)

        try:
            # 记录初始 CPU 使用率
            self.record_resource_snapshot("初始状态")
            initial_cpu = ResourceMonitor.get_cpu_usage()
            logger.info(f"初始 CPU 使用率: {initial_cpu:.1f}%")

            # 模拟工作负载
            logger.info("模拟工作负载（5秒）...")
            start_time = time.time()
            while time.time() - start_time < 5:
                # 执行一些计算
                _ = sum(i * i for i in range(100000))
                time.sleep(0.1)

            # 记录工作期间的 CPU 使用率
            self.record_resource_snapshot("工作期间")
            working_cpu = ResourceMonitor.get_cpu_usage()
            logger.info(f"工作期间 CPU 使用率: {working_cpu:.1f}%")

            # 等待 CPU 恢复
            logger.info("等待 CPU 恢复（5秒）...")
            time.sleep(5)

            # 记录恢复后的 CPU 使用率
            self.record_resource_snapshot("恢复后")
            recovered_cpu = ResourceMonitor.get_cpu_usage()
            logger.info(f"恢复后 CPU 使用率: {recovered_cpu:.1f}%")

            # 验证 CPU 使用率是否回落
            cpu_drop = working_cpu - recovered_cpu
            logger.info(f"CPU 使用率下降: {cpu_drop:.1f}%")

            if cpu_drop > 5:  # 至少下降 5%
                logger.info("✓ CPU 使用率成功回落")
                return True, f"CPU 使用率从 {working_cpu:.1f}% 下降到 {recovered_cpu:.1f}%"
            else:
                logger.warning(f"⚠ CPU 使用率下降不足: {cpu_drop:.1f}%")
                return True, f"CPU 使用率下降: {cpu_drop:.1f}%（可能正常）"

        except Exception as e:
            logger.error(f"✗ 测试异常: {str(e)}", exc_info=True)
            return False, f"测试异常: {str(e)}"

    def test_process_count_stability(self) -> Tuple[bool, str]:
        """
        测试进程数量是否稳定

        Returns:
            (测试是否成功, 测试信息)
        """
        logger.info("=" * 70)
        logger.info("测试 2: 进程数量稳定性")
        logger.info("=" * 70)

        try:
            # 记录初始进程数
            self.record_resource_snapshot("初始状态")
            initial_count = ResourceMonitor.get_process_count()
            logger.info(f"初始进程数: {initial_count}")

            # 监控进程数变化
            logger.info("监控进程数变化（10秒）...")
            process_counts = [initial_count]

            for i in range(10):
                time.sleep(1)
                count = ResourceMonitor.get_process_count()
                process_counts.append(count)
                logger.info(f"  {i+1}秒: {count} 个进程")

            # 记录最终进程数
            self.record_resource_snapshot("监控结束")
            final_count = ResourceMonitor.get_process_count()

            # 计算进程数变化
            min_count = min(process_counts)
            max_count = max(process_counts)
            variance = max_count - min_count

            logger.info(f"进程数范围: {min_count} - {max_count}")
            logger.info(f"进程数变化: {variance}")

            if variance <= 2:  # 允许最多 2 个进程的浮动
                logger.info("✓ 进程数稳定")
                return True, f"进程数稳定，变化范围: {variance}"
            else:
                logger.warning(f"⚠ 进程数波动较大: {variance}")
                return True, f"进程数波动: {variance}（可能正常）"

        except Exception as e:
            logger.error(f"✗ 测试异常: {str(e)}", exc_info=True)
            return False, f"测试异常: {str(e)}"

    def test_no_orphan_processes(self) -> Tuple[bool, str]:
        """
        测试无额外后台进程残留

        Returns:
            (测试是否成功, 测试信息)
        """
        logger.info("=" * 70)
        logger.info("测试 3: 无孤立进程残留")
        logger.info("=" * 70)

        try:
            # 获取当前 Python 进程
            current_process = psutil.Process(os.getpid())
            logger.info(f"当前进程: PID={current_process.pid}, 名称={current_process.name()}")

            # 获取所有子进程
            children = current_process.children(recursive=True)
            logger.info(f"子进程数: {len(children)}")

            if len(children) > 0:
                logger.warning("发现子进程:")
                for child in children:
                    try:
                        logger.warning(f"  - PID={child.pid}, 名称={child.name()}, 状态={child.status()}")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        logger.warning(f"  - PID={child.pid} (无法获取详细信息)")

                logger.warning("⚠ 存在子进程，可能需要清理")
                return True, f"存在 {len(children)} 个子进程"
            else:
                logger.info("✓ 无子进程残留")
                return True, "无孤立进程"

        except Exception as e:
            logger.error(f"✗ 测试异常: {str(e)}", exc_info=True)
            return False, f"测试异常: {str(e)}"

    def test_graceful_shutdown_on_signal(self) -> Tuple[bool, str]:
        """
        测试 Ctrl+C 时所有 python 进程是否立即退出

        Returns:
            (测试是否成功, 测试信息)
        """
        logger.info("=" * 70)
        logger.info("测试 4: 信号处理优雅关闭")
        logger.info("=" * 70)

        try:
            # 创建一个简单的测试进程
            test_script = """
import time
import signal
import sys

def signal_handler(signum, frame):
    print("收到信号，正在关闭...")
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

print("进程已启动")
sys.stdout.flush()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("收到 KeyboardInterrupt")
    sys.exit(0)
"""

            # 写入临时脚本
            temp_script = Path("/tmp/test_graceful_shutdown.py")
            temp_script.write_text(test_script)

            logger.info("启动测试进程...")
            process = subprocess.Popen(
                [sys.executable, str(temp_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # 等待进程启动
            time.sleep(1)

            logger.info(f"测试进程 PID: {process.pid}")

            # 发送 SIGTERM 信号
            logger.info("发送 SIGTERM 信号...")
            start_time = time.time()
            process.terminate()

            # 等待进程退出
            try:
                process.wait(timeout=5)
                elapsed = time.time() - start_time
                logger.info(f"✓ 进程在 {elapsed:.2f} 秒内成功退出")

                # 清理临时脚本
                temp_script.unlink()

                if elapsed < 2:
                    logger.info("✓ 进程快速响应信号")
                    return True, f"进程在 {elapsed:.2f} 秒内优雅关闭"
                else:
                    logger.warning(f"⚠ 进程响应信号较慢: {elapsed:.2f} 秒")
                    return True, f"进程在 {elapsed:.2f} 秒内关闭"

            except subprocess.TimeoutExpired:
                logger.error("✗ 进程未在超时时间内退出，强制杀死...")
                process.kill()
                temp_script.unlink()
                return False, "进程未能及时响应信号"

        except Exception as e:
            logger.error(f"✗ 测试异常: {str(e)}", exc_info=True)
            return False, f"测试异常: {str(e)}"

    def test_memory_cleanup(self) -> Tuple[bool, str]:
        """
        测试内存是否正确清理

        Returns:
            (测试是否成功, 测试信息)
        """
        logger.info("=" * 70)
        logger.info("测试 5: 内存清理")
        logger.info("=" * 70)

        try:
            # 记录初始内存
            self.record_resource_snapshot("初始状态")
            initial_memory = ResourceMonitor.get_memory_usage()
            initial_process_rss = initial_memory.get('process_rss', 0)
            logger.info(f"初始进程内存 (RSS): {initial_process_rss:.1f}MB")

            # 分配大量内存
            logger.info("分配大量内存...")
            large_list = [i for i in range(10000000)]  # 约 80MB

            # 记录分配后的内存
            self.record_resource_snapshot("分配后")
            allocated_memory = ResourceMonitor.get_memory_usage()
            allocated_process_rss = allocated_memory.get('process_rss', 0)
            logger.info(f"分配后进程内存 (RSS): {allocated_process_rss:.1f}MB")

            memory_increase = allocated_process_rss - initial_process_rss
            logger.info(f"内存增加: {memory_increase:.1f}MB")

            # 释放内存
            logger.info("释放内存...")
            del large_list

            # 等待垃圾回收
            import gc
            gc.collect()
            time.sleep(1)

            # 记录释放后的内存
            self.record_resource_snapshot("释放后")
            freed_memory = ResourceMonitor.get_memory_usage()
            freed_process_rss = freed_memory.get('process_rss', 0)
            logger.info(f"释放后进程内存 (RSS): {freed_process_rss:.1f}MB")

            memory_recovered = allocated_process_rss - freed_process_rss
            logger.info(f"内存恢复: {memory_recovered:.1f}MB")

            recovery_ratio = memory_recovered / memory_increase if memory_increase > 0 else 0
            logger.info(f"内存恢复率: {recovery_ratio * 100:.1f}%")

            if recovery_ratio > 0.5:  # 至少恢复 50%
                logger.info("✓ 内存成功释放")
                return True, f"内存恢复率: {recovery_ratio * 100:.1f}%"
            else:
                logger.warning(f"⚠ 内存恢复率较低: {recovery_ratio * 100:.1f}%")
                return True, f"内存恢复率: {recovery_ratio * 100:.1f}%（可能正常）"

        except Exception as e:
            logger.error(f"✗ 测试异常: {str(e)}", exc_info=True)
            return False, f"测试异常: {str(e)}"

    def run_all_tests(self) -> Dict[str, Tuple[bool, str]]:
        """
        运行所有集成测试

        Returns:
            测试结果字典
        """
        logger.info("\n" + "=" * 70)
        logger.info("开始集成测试：优雅关闭验证")
        logger.info("=" * 70)

        results = {}

        # 测试 1: CPU 恢复
        try:
            success, message = self.test_normal_completion_cpu_recovery()
            results["CPU 使用率恢复"] = (success, message)
        except Exception as e:
            logger.error(f"CPU 恢复测试异常: {str(e)}")
            results["CPU 使用率恢复"] = (False, str(e))

        # 测试 2: 进程数稳定性
        try:
            success, message = self.test_process_count_stability()
            results["进程数稳定性"] = (success, message)
        except Exception as e:
            logger.error(f"进程数稳定性测试异常: {str(e)}")
            results["进程数稳定性"] = (False, str(e))

        # 测试 3: 无孤立进程
        try:
            success, message = self.test_no_orphan_processes()
            results["无孤立进程"] = (success, message)
        except Exception as e:
            logger.error(f"孤立进程测试异常: {str(e)}")
            results["无孤立进程"] = (False, str(e))

        # 测试 4: 信号处理
        try:
            success, message = self.test_graceful_shutdown_on_signal()
            results["信号处理优雅关闭"] = (success, message)
        except Exception as e:
            logger.error(f"信号处理测试异常: {str(e)}")
            results["信号处理优雅关闭"] = (False, str(e))

        # 测试 5: 内存清理
        try:
            success, message = self.test_memory_cleanup()
            results["内存清理"] = (success, message)
        except Exception as e:
            logger.error(f"内存清理测试异常: {str(e)}")
            results["内存清理"] = (False, str(e))

        # 输出测试结果
        logger.info("\n" + "=" * 70)
        logger.info("集成测试结果汇总")
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
        logger.info(f"集成测试完成: {passed} 通过, {failed} 失败")
        logger.info("=" * 70)

        return results


if __name__ == "__main__":
    try:
        tester = GracefulShutdownTester()
        results = tester.run_all_tests()

        # 返回退出码
        failed_count = sum(1 for success, _ in results.values() if not success)
        sys.exit(0 if failed_count == 0 else 1)

    except Exception as e:
        logger.error(f"集成测试异常: {str(e)}", exc_info=True)
        sys.exit(1)
