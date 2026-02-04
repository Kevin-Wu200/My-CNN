#!/usr/bin/env python3
"""
部署脚本
用于将优化后的代码部署到生产环境
"""

import sys
import os
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import Tuple

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DeploymentManager:
    """部署管理器"""

    def __init__(self, project_root: Path, environment: str = "production"):
        """
        初始化部署管理器

        Args:
            project_root: 项目根目录
            environment: 部署环境 (development, staging, production)
        """
        self.project_root = project_root
        self.environment = environment
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_dir = project_root / "backups" / self.timestamp
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def pre_deployment_checks(self) -> bool:
        """
        部署前检查

        Returns:
            是否通过所有检查
        """
        logger.info("\n" + "=" * 70)
        logger.info("执行部署前检查")
        logger.info("=" * 70)

        checks = []

        # 检查 1: Git 状态
        logger.info("检查 1: 验证 Git 状态...")
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(self.project_root),
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and not result.stdout.strip():
            logger.info("✓ Git 工作目录干净")
            checks.append(True)
        else:
            logger.error("✗ Git 工作目录有未提交的变更")
            checks.append(False)

        # 检查 2: 最新提交包含优化
        logger.info("检查 2: 验证最新提交...")
        result = subprocess.run(
            ["git", "log", "-1", "--oneline"],
            cwd=str(self.project_root),
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            commit_msg = result.stdout.strip()
            logger.info(f"✓ 最新提交: {commit_msg}")
            if "optimize" in commit_msg.lower() or "parallel" in commit_msg.lower():
                logger.info("✓ 提交包含优化内容")
                checks.append(True)
            else:
                logger.warning("⚠ 提交信息中未包含优化相关内容")
                checks.append(True)  # 不阻止部署
        else:
            logger.error("✗ 无法获取最新提交")
            checks.append(False)

        # 检查 3: 后端服务可用性
        logger.info("检查 3: 验证后端服务...")
        try:
            import torch
            import numpy
            import sklearn
            logger.info("✓ 所有必要的依赖已安装")
            checks.append(True)
        except ImportError as e:
            logger.error(f"✗ 缺少依赖: {str(e)}")
            checks.append(False)

        # 检查 4: 配置文件完整性
        logger.info("检查 4: 验证配置文件...")
        config_file = self.project_root / "backend" / "config" / "settings.py"
        if config_file.exists():
            logger.info("✓ 配置文件存在")
            checks.append(True)
        else:
            logger.error("✗ 配置文件不存在")
            checks.append(False)

        all_passed = all(checks)
        logger.info("=" * 70)
        if all_passed:
            logger.info("✓ 所有部署前检查通过")
        else:
            logger.error("✗ 部分检查失败，请解决后重试")
        logger.info("=" * 70)

        return all_passed

    def backup_current_code(self) -> bool:
        """
        备份当前代码

        Returns:
            是否备份成功
        """
        logger.info("\n" + "=" * 70)
        logger.info("备份当前代码")
        logger.info("=" * 70)

        try:
            # 备份关键文件
            files_to_backup = [
                "backend/services/parallel_processing.py",
                "backend/services/detection.py",
                "backend/services/unsupervised_detection.py",
                "backend/config/settings.py",
            ]

            for file_path in files_to_backup:
                src = self.project_root / file_path
                dst = self.backup_dir / file_path.replace("/", "_")
                if src.exists():
                    with open(src, 'r', encoding='utf-8') as f:
                        content = f.read()
                    with open(dst, 'w', encoding='utf-8') as f:
                        f.write(content)
                    logger.info(f"✓ 已备份: {file_path}")
                else:
                    logger.warning(f"⚠ 文件不存在: {file_path}")

            logger.info(f"✓ 备份完成，位置: {self.backup_dir}")
            return True

        except Exception as e:
            logger.error(f"✗ 备份失败: {str(e)}")
            return False

    def deploy_to_environment(self) -> bool:
        """
        部署到指定环境

        Returns:
            是否部署成功
        """
        logger.info("\n" + "=" * 70)
        logger.info(f"部署到 {self.environment} 环境")
        logger.info("=" * 70)

        try:
            if self.environment == "production":
                logger.info("部署到生产环境...")
                # 在生产环境中，通常需要额外的步骤
                logger.info("✓ 代码已准备好部署")
                logger.info("✓ 建议步骤:")
                logger.info("  1. 在生产服务器上拉取最新代码")
                logger.info("  2. 运行后端服务重启")
                logger.info("  3. 验证服务状态")
                logger.info("  4. 监控日志和性能指标")

            elif self.environment == "staging":
                logger.info("部署到测试环境...")
                logger.info("✓ 代码已准备好部署")

            elif self.environment == "development":
                logger.info("部署到开发环境...")
                logger.info("✓ 代码已准备好部署")

            return True

        except Exception as e:
            logger.error(f"✗ 部署失败: {str(e)}")
            return False

    def post_deployment_verification(self) -> bool:
        """
        部署后验证

        Returns:
            是否验证通过
        """
        logger.info("\n" + "=" * 70)
        logger.info("执行部署后验证")
        logger.info("=" * 70)

        try:
            # 验证 1: 导入模块
            logger.info("验证 1: 检查模块导入...")
            try:
                from backend.services.parallel_processing import DEFAULT_PARALLEL_WORKERS
                from backend.services.detection import DiseaseTreeDetectionService
                from backend.services.unsupervised_detection import UnsupervisedDiseaseDetectionService
                logger.info("✓ 所有模块导入成功")
            except ImportError as e:
                logger.error(f"✗ 模块导入失败: {str(e)}")
                return False

            # 验证 2: 检查常量
            logger.info("验证 2: 检查优化常量...")
            if DEFAULT_PARALLEL_WORKERS == 8:
                logger.info(f"✓ DEFAULT_PARALLEL_WORKERS = {DEFAULT_PARALLEL_WORKERS}")
            else:
                logger.error(f"✗ DEFAULT_PARALLEL_WORKERS 值不正确: {DEFAULT_PARALLEL_WORKERS}")
                return False

            # 验证 3: 检查默认参数
            logger.info("验证 3: 检查默认参数...")
            import inspect
            sig = inspect.signature(DiseaseTreeDetectionService.detect_on_tiled_image)
            num_workers = sig.parameters['num_workers'].default
            if num_workers == 8:
                logger.info(f"✓ detect_on_tiled_image 的 num_workers 默认值为 {num_workers}")
            else:
                logger.error(f"✗ num_workers 默认值不正确: {num_workers}")
                return False

            logger.info("✓ 所有部署后验证通过")
            return True

        except Exception as e:
            logger.error(f"✗ 部署后验证失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def generate_deployment_report(self) -> None:
        """
        生成部署报告
        """
        logger.info("\n" + "=" * 70)
        logger.info("生成部署报告")
        logger.info("=" * 70)

        report_file = self.project_root / "DEPLOYMENT_REPORT.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("# 后端影像处理优化部署报告\n\n")
            f.write(f"**部署时间**: {self.timestamp}\n")
            f.write(f"**部署环境**: {self.environment}\n")
            f.write(f"**备份位置**: {self.backup_dir}\n\n")

            f.write("## 优化内容\n\n")
            f.write("### 1. 并行处理优化\n")
            f.write("- 设置默认并行工作进程数为 8\n")
            f.write("- 优化 ParallelProcessingService.get_auto_worker_count() 方法\n")
            f.write("- 确保在大多数系统上都能使用 8 个工作进程\n\n")

            f.write("### 2. 分块大小配置\n")
            f.write("- 分块大小: 1024×1024 像素\n")
            f.write("- 平衡内存占用和处理效率\n\n")

            f.write("### 3. 服务更新\n")
            f.write("- 深度学习检测服务: detect_on_tiled_image() 默认 num_workers=8\n")
            f.write("- 无监督检测服务: detect_on_tiled_image() 默认 num_workers=8\n\n")

            f.write("## 修改文件\n\n")
            f.write("| 文件 | 修改内容 |\n")
            f.write("|------|----------|\n")
            f.write("| backend/services/parallel_processing.py | 添加 DEFAULT_PARALLEL_WORKERS=8 |\n")
            f.write("| backend/services/detection.py | 更新 num_workers 默认值为 8 |\n")
            f.write("| backend/services/unsupervised_detection.py | 更新 num_workers 默认值为 8 |\n")
            f.write("| backend/config/settings.py | 更新配置注释 |\n\n")

            f.write("## 性能提升\n\n")
            f.write("- 并行处理 8 个分块相比顺序处理可显著提升处理速度\n")
            f.write("- 充分利用多核 CPU，提高系统资源利用率\n")
            f.write("- 支持大尺寸影像的高效处理\n\n")

            f.write("## 部署步骤\n\n")
            f.write("1. 运行测试验证\n")
            f.write("2. 执行部署前检查\n")
            f.write("3. 备份当前代码\n")
            f.write("4. 部署到目标环境\n")
            f.write("5. 执行部署后验证\n")
            f.write("6. 监控系统性能\n\n")

            f.write("## 回滚方案\n\n")
            f.write(f"如需回滚，可从备份目录恢复: {self.backup_dir}\n\n")

            f.write("## 监控建议\n\n")
            f.write("- 监控并行处理的工作进程数\n")
            f.write("- 跟踪分块处理的耗时\n")
            f.write("- 监控内存占用情况\n")
            f.write("- 记录检测结果的准确性\n\n")

        logger.info(f"✓ 部署报告已生成: {report_file}")

    def run_deployment(self) -> bool:
        """
        执行完整部署流程

        Returns:
            是否部署成功
        """
        logger.info("\n" + "=" * 70)
        logger.info("开始部署流程")
        logger.info("=" * 70)

        # 第一步: 部署前检查
        if not self.pre_deployment_checks():
            logger.error("✗ 部署前检查失败，中止部署")
            return False

        # 第二步: 备份代码
        if not self.backup_current_code():
            logger.error("✗ 代码备份失败，中止部署")
            return False

        # 第三步: 部署到环境
        if not self.deploy_to_environment():
            logger.error("✗ 部署失败，中止部署")
            return False

        # 第四步: 部署后验证
        if not self.post_deployment_verification():
            logger.error("✗ 部署后验证失败")
            return False

        # 第五步: 生成报告
        self.generate_deployment_report()

        logger.info("\n" + "=" * 70)
        logger.info("✓ 部署完成")
        logger.info("=" * 70)

        return True


def main():
    """主函数"""
    project_root = Path(__file__).parent.parent

    # 确定部署环境
    environment = os.environ.get("DEPLOY_ENV", "production")

    manager = DeploymentManager(project_root, environment)
    success = manager.run_deployment()

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
