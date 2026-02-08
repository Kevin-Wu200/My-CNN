#!/usr/bin/env python3
"""
后端服务稳定性验证脚本

验证内容：
1. 服务进程 PID 不发生变化
2. 端口 8000 始终可连接
3. /health 端点始终可访问
4. 日志中不出现 "Stopping reloader process"
"""

import requests
import time
import subprocess
import os
import signal
import sys
from pathlib import Path
from datetime import datetime

# 配置
BACKEND_URL = "http://localhost:8000"
HEALTH_CHECK_INTERVAL = 2  # 秒
VERIFICATION_DURATION = 60  # 验证持续时间（秒）
LOG_FILE = "/Users/wuchenkai/深度学习模型/logs/backend.log"

class BackendStabilityVerifier:
    """后端服务稳定性验证器"""

    def __init__(self):
        """初始化验证器"""
        self.initial_pid = None
        self.health_check_count = 0
        self.health_check_failures = 0
        self.pid_changes = []
        self.start_time = None
        self.end_time = None

    def get_backend_pid(self) -> int:
        """获取后端服务进程 PID"""
        try:
            result = subprocess.run(
                ["lsof", "-i", ":8000", "-t"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                return int(pids[0])
        except Exception as e:
            print(f"❌ 获取 PID 失败: {e}")
        return None

    def check_health(self) -> bool:
        """检查服务健康状态"""
        try:
            response = requests.get(
                f"{BACKEND_URL}/health",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                if status == "healthy":
                    return True
        except Exception as e:
            print(f"  ⚠️  健康检查失败: {e}")
            self.health_check_failures += 1
        return False

    def check_reloader_in_logs(self) -> bool:
        """检查日志中是否出现 reloader 相关信息"""
        if not os.path.exists(LOG_FILE):
            return False

        try:
            with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                if "Stopping reloader process" in content:
                    return True
                if "reloader" in content.lower():
                    return True
        except Exception as e:
            print(f"  ⚠️  读取日志失败: {e}")

        return False

    def verify(self):
        """执行验证"""
        print("\n" + "="*60)
        print("后端服务稳定性验证")
        print("="*60)

        self.start_time = datetime.now()
        print(f"\n⏱️  验证开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📊 验证持续时间: {VERIFICATION_DURATION} 秒")
        print(f"🔄 健康检查间隔: {HEALTH_CHECK_INTERVAL} 秒")

        # 获取初始 PID
        print("\n🔍 获取初始服务 PID...")
        self.initial_pid = self.get_backend_pid()
        if not self.initial_pid:
            print("❌ 无法获取后端服务 PID，请确保服务已启动")
            return False

        print(f"✅ 初始 PID: {self.initial_pid}")

        # 执行健康检查
        print(f"\n🏥 开始健康检查（每 {HEALTH_CHECK_INTERVAL} 秒一次）...")
        print("-" * 60)

        elapsed = 0
        while elapsed < VERIFICATION_DURATION:
            current_pid = self.get_backend_pid()

            if current_pid != self.initial_pid:
                self.pid_changes.append({
                    'time': elapsed,
                    'old_pid': self.initial_pid,
                    'new_pid': current_pid
                })
                print(f"⚠️  [{elapsed}s] PID 变化: {self.initial_pid} → {current_pid}")
                self.initial_pid = current_pid

            # 检查健康状态
            is_healthy = self.check_health()
            self.health_check_count += 1

            status_icon = "✅" if is_healthy else "❌"
            print(f"{status_icon} [{elapsed}s] 健康检查 #{self.health_check_count}: {'成功' if is_healthy else '失败'}")

            time.sleep(HEALTH_CHECK_INTERVAL)
            elapsed += HEALTH_CHECK_INTERVAL

        self.end_time = datetime.now()

        # 生成报告
        print("\n" + "="*60)
        print("验证报告")
        print("="*60)

        print(f"\n⏱️  验证结束时间: {self.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏳ 总耗时: {(self.end_time - self.start_time).total_seconds():.1f} 秒")

        print(f"\n📊 健康检查统计:")
        print(f"  • 总检查次数: {self.health_check_count}")
        print(f"  • 成功次数: {self.health_check_count - self.health_check_failures}")
        print(f"  • 失败次数: {self.health_check_failures}")

        if self.health_check_failures > 0:
            success_rate = ((self.health_check_count - self.health_check_failures) / self.health_check_count) * 100
            print(f"  • 成功率: {success_rate:.1f}%")
        else:
            print(f"  • 成功率: 100%")

        print(f"\n🔄 PID 变化:")
        if self.pid_changes:
            print(f"  ❌ 检测到 {len(self.pid_changes)} 次 PID 变化:")
            for change in self.pid_changes:
                print(f"     • [{change['time']}s] {change['old_pid']} → {change['new_pid']}")
        else:
            print(f"  ✅ 未检测到 PID 变化")

        print(f"\n📝 日志检查:")
        has_reloader = self.check_reloader_in_logs()
        if has_reloader:
            print(f"  ❌ 日志中发现 reloader 相关信息")
        else:
            print(f"  ✅ 日志中未发现 reloader 相关信息")

        # 验收标准
        print("\n" + "="*60)
        print("验收标准检查")
        print("="*60)

        criteria = [
            ("后端服务始终可达", self.health_check_failures == 0),
            ("日志中不出现 reloader", not has_reloader),
            ("服务 PID 不变化", len(self.pid_changes) == 0),
        ]

        all_passed = True
        for criterion, passed in criteria:
            icon = "✅" if passed else "❌"
            print(f"{icon} {criterion}")
            if not passed:
                all_passed = False

        print("\n" + "="*60)
        if all_passed:
            print("✅ 所有验收标准已通过！")
            print("="*60)
            return True
        else:
            print("❌ 部分验收标准未通过，请检查上述错误")
            print("="*60)
            return False

def main():
    """主函数"""
    verifier = BackendStabilityVerifier()

    try:
        success = verifier.verify()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  验证被中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 验证过程中发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
