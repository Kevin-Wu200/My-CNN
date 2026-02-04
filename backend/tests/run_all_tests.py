"""
测试运行器脚本
用于执行所有验证测试并生成综合报告
"""

import os
import sys
import time
import subprocess
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.utils.logger import LoggerSetup

# 设置日志
logger = LoggerSetup.setup_logger("test_runner", log_dir=Path("./logs/test_runner"))


class TestRunner:
    """测试运行器"""

    def __init__(self):
        """初始化测试运行器"""
        self.test_results = {}
        self.start_time = None
        self.end_time = None
        self.backend_tests_dir = Path(__file__).parent

    def run_test_script(self, script_name: str, script_path: Path) -> Tuple[bool, str, float]:
        """
        运行单个测试脚本

        Args:
            script_name: 脚本名称
            script_path: 脚本路径

        Returns:
            (是否成功, 输出信息, 执行时间)
        """
        logger.info("=" * 70)
        logger.info(f"运行测试: {script_name}")
        logger.info("=" * 70)

        try:
            if not script_path.exists():
                logger.error(f"✗ 测试脚本不存在: {script_path}")
                return False, f"脚本不存在: {script_path}", 0

            # 运行测试脚本
            start_time = time.time()
            logger.info(f"执行命令: python {script_path}")

            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=600  # 10 分钟超时
            )

            elapsed = time.time() - start_time

            # 记录输出
            if result.stdout:
                logger.info("标准输出:")
                logger.info(result.stdout)

            if result.stderr:
                logger.warning("标准错误:")
                logger.warning(result.stderr)

            # 检查返回码
            if result.returncode == 0:
                logger.info(f"✓ 测试通过，耗时: {elapsed:.2f} 秒")
                return True, "测试通过", elapsed
            else:
                logger.error(f"✗ 测试失败，返回码: {result.returncode}，耗时: {elapsed:.2f} 秒")
                return False, f"测试失败，返回码: {result.returncode}", elapsed

        except subprocess.TimeoutExpired:
            logger.error(f"✗ 测试超时（10 分钟）")
            return False, "测试超时", 600

        except Exception as e:
            logger.error(f"✗ 测试异常: {str(e)}", exc_info=True)
            return False, f"测试异常: {str(e)}", 0

    def run_all_tests(self) -> Dict[str, Tuple[bool, str, float]]:
        """
        运行所有测试

        Returns:
            测试结果字典
        """
        logger.info("\n" + "=" * 70)
        logger.info("开始运行所有验证测试")
        logger.info("=" * 70)

        self.start_time = datetime.now()

        # 定义测试脚本
        test_scripts = [
            ("基础功能验证", self.backend_tests_dir / "verify_fixes.py"),
            ("集成测试验证", self.backend_tests_dir / "integration_test_graceful_shutdown.py"),
            ("压力测试验证", self.backend_tests_dir / "stress_test_parallel_processing.py"),
        ]

        # 运行每个测试脚本
        for test_name, script_path in test_scripts:
            try:
                success, message, elapsed = self.run_test_script(test_name, script_path)
                self.test_results[test_name] = (success, message, elapsed)
            except Exception as e:
                logger.error(f"运行 {test_name} 异常: {str(e)}")
                self.test_results[test_name] = (False, str(e), 0)

            # 测试之间的间隔
            time.sleep(2)

        self.end_time = datetime.now()

        # 输出测试结果汇总
        self.print_summary()

        return self.test_results

    def print_summary(self) -> None:
        """输出测试结果汇总"""
        logger.info("\n" + "=" * 70)
        logger.info("测试结果汇总")
        logger.info("=" * 70)

        passed = 0
        failed = 0
        total_time = 0

        for test_name, (success, message, elapsed) in self.test_results.items():
            status = "✓ 通过" if success else "✗ 失败"
            logger.info(f"{status}: {test_name}")
            logger.info(f"  - 信息: {message}")
            logger.info(f"  - 耗时: {elapsed:.2f} 秒")

            if success:
                passed += 1
            else:
                failed += 1

            total_time += elapsed

        logger.info("=" * 70)
        logger.info(f"总体结果: {passed} 通过, {failed} 失败")
        logger.info(f"总耗时: {total_time:.2f} 秒")

        if self.start_time and self.end_time:
            total_duration = (self.end_time - self.start_time).total_seconds()
            logger.info(f"总运行时间: {total_duration:.2f} 秒")

        logger.info("=" * 70)

    def generate_json_report(self, output_path: Path = None) -> Path:
        """
        生成 JSON 格式的测试报告

        Args:
            output_path: 输出路径

        Returns:
            报告文件路径
        """
        if output_path is None:
            output_path = Path("./test_results.json")

        report = {
            "timestamp": datetime.now().isoformat(),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "tests": {}
        }

        for test_name, (success, message, elapsed) in self.test_results.items():
            report["tests"][test_name] = {
                "success": success,
                "message": message,
                "elapsed": elapsed
            }

        # 计算统计信息
        total_tests = len(self.test_results)
        passed_tests = sum(1 for success, _, _ in self.test_results.values() if success)
        failed_tests = total_tests - passed_tests

        report["summary"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "pass_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0
        }

        # 写入 JSON 文件
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            logger.info(f"✓ JSON 报告已生成: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"✗ 生成 JSON 报告失败: {str(e)}")
            return None

    def generate_html_report(self, output_path: Path = None) -> Path:
        """
        生成 HTML 格式的测试报告

        Args:
            output_path: 输出路径

        Returns:
            报告文件路径
        """
        if output_path is None:
            output_path = Path("./test_results.html")

        # 计算统计信息
        total_tests = len(self.test_results)
        passed_tests = sum(1 for success, _, _ in self.test_results.values() if success)
        failed_tests = total_tests - passed_tests
        pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        # 生成 HTML 内容
        html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>验证测试报告</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 30px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin: 20px 0;
        }}
        .summary-item {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            text-align: center;
            border-left: 4px solid #007bff;
        }}
        .summary-item.passed {{
            border-left-color: #28a745;
        }}
        .summary-item.failed {{
            border-left-color: #dc3545;
        }}
        .summary-item h3 {{
            margin: 0 0 10px 0;
            color: #666;
            font-size: 14px;
        }}
        .summary-item .value {{
            font-size: 28px;
            font-weight: bold;
            color: #333;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th {{
            background-color: #007bff;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: bold;
        }}
        td {{
            padding: 12px;
            border-bottom: 1px solid #ddd;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .status-pass {{
            color: #28a745;
            font-weight: bold;
        }}
        .status-fail {{
            color: #dc3545;
            font-weight: bold;
        }}
        .progress-bar {{
            width: 100%;
            height: 20px;
            background-color: #e9ecef;
            border-radius: 10px;
            overflow: hidden;
        }}
        .progress-fill {{
            height: 100%;
            background-color: #28a745;
            text-align: center;
            color: white;
            font-size: 12px;
            line-height: 20px;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #666;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>验证测试报告</h1>

        <div class="summary">
            <div class="summary-item">
                <h3>总测试数</h3>
                <div class="value">{total_tests}</div>
            </div>
            <div class="summary-item passed">
                <h3>通过</h3>
                <div class="value">{passed_tests}</div>
            </div>
            <div class="summary-item failed">
                <h3>失败</h3>
                <div class="value">{failed_tests}</div>
            </div>
            <div class="summary-item">
                <h3>通过率</h3>
                <div class="value">{pass_rate:.1f}%</div>
            </div>
        </div>

        <h2>通过率</h2>
        <div class="progress-bar">
            <div class="progress-fill" style="width: {pass_rate}%">{pass_rate:.1f}%</div>
        </div>

        <h2>详细结果</h2>
        <table>
            <thead>
                <tr>
                    <th>测试名称</th>
                    <th>状态</th>
                    <th>信息</th>
                    <th>耗时 (秒)</th>
                </tr>
            </thead>
            <tbody>
"""

        for test_name, (success, message, elapsed) in self.test_results.items():
            status_class = "status-pass" if success else "status-fail"
            status_text = "通过" if success else "失败"
            html_content += f"""
                <tr>
                    <td>{test_name}</td>
                    <td><span class="{status_class}">{status_text}</span></td>
                    <td>{message}</td>
                    <td>{elapsed:.2f}</td>
                </tr>
"""

        html_content += """
            </tbody>
        </table>

        <div class="footer">
            <p>报告生成时间: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
            <p>项目: 深度学习模型 - 病害木检测系统</p>
        </div>
    </div>
</body>
</html>
"""

        # 写入 HTML 文件
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            logger.info(f"✓ HTML 报告已生成: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"✗ 生成 HTML 报告失败: {str(e)}")
            return None


def main():
    """主函数"""
    logger.info("\n" + "=" * 70)
    logger.info("验证测试运行器")
    logger.info("=" * 70)

    try:
        # 创建测试运行器
        runner = TestRunner()

        # 运行所有测试
        results = runner.run_all_tests()

        # 生成报告
        logger.info("\n生成测试报告...")
        json_report = runner.generate_json_report(Path("./test_results.json"))
        html_report = runner.generate_html_report(Path("./test_results.html"))

        logger.info(f"✓ 测试报告已生成:")
        if json_report:
            logger.info(f"  - JSON 报告: {json_report}")
        if html_report:
            logger.info(f"  - HTML 报告: {html_report}")

        # 返回退出码
        failed_count = sum(1 for success, _, _ in results.values() if not success)
        sys.exit(0 if failed_count == 0 else 1)

    except Exception as e:
        logger.error(f"测试运行异常: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
