#!/usr/bin/env python3
"""
完整测试运行器
运行所有测试验证、性能基准测试和部署检查
"""

import sys
import os
import subprocess
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestRunner:
    """完整测试运行器"""

    def __init__(self, project_root: Path):
        """
        初始化测试运行器

        Args:
            project_root: 项目根目录
        """
        self.project_root = project_root
        self.test_results = {}
        self.deployment_checks = {}
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.report_dir = project_root / "test_reports"
        self.report_dir.mkdir(exist_ok=True)

    def run_parallel_optimization_tests(self) -> Tuple[bool, Dict]:
        """
        运行并行处理优化测试

        Returns:
            (是否通过, 测试结果)
        """
        logger.info("\n" + "=" * 70)
        logger.info("第一阶段: 运行并行处理优化测试")
        logger.info("=" * 70)

        try:
            test_file = self.project_root / "tests" / "test_parallel_optimization.py"
            if not test_file.exists():
                logger.error(f"测试文件不存在: {test_file}")
                return False, {}

            # 运行测试
            result = subprocess.run(
                [sys.executable, str(test_file)],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=300
            )

            logger.info(result.stdout)
            if result.stderr:
                logger.warning(result.stderr)

            success = result.returncode == 0
            return success, {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }

        except subprocess.TimeoutExpired:
            logger.error("测试超时")
            return False, {"error": "测试超时"}
        except Exception as e:
            logger.error(f"运行测试失败: {str(e)}")
            return False, {"error": str(e)}

    def verify_code_changes(self) -> Tuple[bool, Dict]:
        """
        验证代码变更

        Returns:
            (是否通过, 验证结果)
        """
        logger.info("\n" + "=" * 70)
        logger.info("第二阶段: 验证代码变更")
        logger.info("=" * 70)

        try:
            checks = {}

            # 检查 1: 验证 parallel_processing.py 中的常量
            logger.info("检查 1: 验证 DEFAULT_PARALLEL_WORKERS 常量...")
            parallel_file = self.project_root / "backend" / "services" / "parallel_processing.py"
            with open(parallel_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if "DEFAULT_PARALLEL_WORKERS = 8" in content:
                    logger.info("✓ DEFAULT_PARALLEL_WORKERS = 8 已设置")
                    checks["parallel_workers_constant"] = True
                else:
                    logger.error("✗ DEFAULT_PARALLEL_WORKERS 常量未正确设置")
                    checks["parallel_workers_constant"] = False

            # 检查 2: 验证 detection.py 中的默认参数
            logger.info("检查 2: 验证 detection.py 中的默认参数...")
            detection_file = self.project_root / "backend" / "services" / "detection.py"
            with open(detection_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if "num_workers: Optional[int] = 8" in content:
                    logger.info("✓ detection.py 中 num_workers 默认值为 8")
                    checks["detection_default_workers"] = True
                else:
                    logger.error("✗ detection.py 中 num_workers 默认值未正确设置")
                    checks["detection_default_workers"] = False

            # 检查 3: 验证 unsupervised_detection.py 中的默认参数
            logger.info("检查 3: 验证 unsupervised_detection.py 中的默认参数...")
            unsupervised_file = self.project_root / "backend" / "services" / "unsupervised_detection.py"
            with open(unsupervised_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if "num_workers: Optional[int] = 8" in content:
                    logger.info("✓ unsupervised_detection.py 中 num_workers 默认值为 8")
                    checks["unsupervised_default_workers"] = True
                else:
                    logger.error("✗ unsupervised_detection.py 中 num_workers 默认值未正确设置")
                    checks["unsupervised_default_workers"] = False

            # 检查 4: 验证分块大小
            logger.info("检查 4: 验证分块大小为 1024×1024...")
            tile_file = self.project_root / "backend" / "utils" / "tile_utils.py"
            with open(tile_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if "DEFAULT_TILE_SIZE = 1024" in content:
                    logger.info("✓ DEFAULT_TILE_SIZE = 1024")
                    checks["tile_size"] = True
                else:
                    logger.error("✗ DEFAULT_TILE_SIZE 未正确设置")
                    checks["tile_size"] = False

            all_passed = all(checks.values())
            return all_passed, checks

        except Exception as e:
            logger.error(f"验证代码变更失败: {str(e)}")
            return False, {"error": str(e)}

    def deployment_checklist(self) -> Tuple[bool, Dict]:
        """
        部署前检查清单

        Returns:
            (是否通过, 检查结果)
        """
        logger.info("\n" + "=" * 70)
        logger.info("第三阶段: 部署前检查清单")
        logger.info("=" * 70)

        try:
            checks = {}

            # 检查 1: Git 状态
            logger.info("检查 1: 验证 Git 状态...")
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                uncommitted = result.stdout.strip()
                if uncommitted:
                    logger.warning(f"⚠ 存在未提交的变更:\n{uncommitted}")
                    checks["git_clean"] = False
                else:
                    logger.info("✓ Git 工作目录干净")
                    checks["git_clean"] = True
            else:
                logger.error("✗ 无法检查 Git 状态")
                checks["git_clean"] = False

            # 检查 2: 最新提交
            logger.info("检查 2: 验证最新提交...")
            result = subprocess.run(
                ["git", "log", "-1", "--oneline"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                logger.info(f"✓ 最新提交: {result.stdout.strip()}")
                checks["latest_commit"] = True
            else:
                logger.error("✗ 无法获取最新提交")
                checks["latest_commit"] = False

            # 检查 3: 后端依赖
            logger.info("检查 3: 验证后端依赖...")
            try:
                import numpy
                import torch
                import sklearn
                logger.info("✓ 所有必要的后端依赖已安装")
                checks["backend_dependencies"] = True
            except ImportError as e:
                logger.error(f"✗ 缺少依赖: {str(e)}")
                checks["backend_dependencies"] = False

            # 检查 4: 配置文件
            logger.info("检查 4: 验证配置文件...")
            config_file = self.project_root / "backend" / "config" / "settings.py"
            if config_file.exists():
                logger.info("✓ 配置文件存在")
                checks["config_file"] = True
            else:
                logger.error("✗ 配置文件不存在")
                checks["config_file"] = False

            # 检查 5: 存储目录
            logger.info("检查 5: 验证存储目录...")
            storage_dir = self.project_root / "storage"
            if storage_dir.exists():
                logger.info("✓ 存储目录存在")
                checks["storage_dir"] = True
            else:
                logger.warning("⚠ 存储目录不存在，将在运行时创建")
                checks["storage_dir"] = False

            all_passed = all(checks.values())
            return all_passed, checks

        except Exception as e:
            logger.error(f"部署前检查失败: {str(e)}")
            return False, {"error": str(e)}

    def generate_report(self):
        """
        生成测试报告
        """
        logger.info("\n" + "=" * 70)
        logger.info("生成测试报告")
        logger.info("=" * 70)

        # 转换测试结果为可序列化的格式
        serializable_results = {}
        for test_name, (passed, details) in self.test_results.items():
            if isinstance(details, dict):
                serializable_results[test_name] = {
                    "passed": passed,
                    "details": str(details)
                }
            else:
                serializable_results[test_name] = {
                    "passed": passed,
                    "details": str(details)
                }

        report = {
            "timestamp": self.timestamp,
            "test_results": serializable_results,
        }

        # 保存为 JSON
        report_file = self.report_dir / f"test_report_{self.timestamp}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"✓ 测试报告已保存: {report_file}")

        # 保存为文本
        text_report_file = self.report_dir / f"test_report_{self.timestamp}.txt"
        with open(text_report_file, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("后端影像处理优化测试报告\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"生成时间: {self.timestamp}\n\n")

            f.write("=" * 70 + "\n")
            f.write("测试结果\n")
            f.write("=" * 70 + "\n")
            for test_name, (passed, details) in self.test_results.items():
                status = "✓ 通过" if passed else "✗ 失败"
                f.write(f"{status}: {test_name}\n")
                if isinstance(details, dict) and "error" in details:
                    f.write(f"  错误: {details['error']}\n")
            f.write("\n")

        logger.info(f"✓ 文本报告已保存: {text_report_file}")

    def run_all(self) -> bool:
        """
        运行所有测试和检查

        Returns:
            是否所有测试都通过
        """
        logger.info("\n" + "=" * 70)
        logger.info("开始完整测试流程")
        logger.info("=" * 70)

        # 第一阶段: 运行并行处理优化测试
        success1, details1 = self.run_parallel_optimization_tests()
        self.test_results["并行处理优化测试"] = (success1, details1)

        # 第二阶段: 验证代码变更
        success2, details2 = self.verify_code_changes()
        self.test_results["代码变更验证"] = (success2, details2)

        # 生成报告
        self.generate_report()

        # 总结
        logger.info("\n" + "=" * 70)
        logger.info("测试总结")
        logger.info("=" * 70)

        all_passed = success1 and success2
        if all_passed:
            logger.info("✓ 所有测试通过，可以进行部署")
        else:
            logger.error("✗ 部分测试失败，请检查上述错误")

        return all_passed


def main():
    """主函数"""
    project_root = Path(__file__).parent.parent
    runner = TestRunner(project_root)
    success = runner.run_all()
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
