#!/usr/bin/env python3
"""
自动环境配置脚本
用于自动创建虚拟环境并安装项目依赖

兼容 Windows / macOS / Linux
仅使用 Python 标准库，无需第三方依赖
"""

import os
import sys
import subprocess
import platform
from pathlib import Path


class EnvironmentSetup:
    """环境配置类"""

    def __init__(self):
        """初始化环境配置"""
        self.project_root = Path(__file__).parent.absolute()
        self.venv_dir = self.project_root / "venv"
        self.requirements_file = self.project_root / "requirements.txt"
        self.python_executable = sys.executable
        self.system = platform.system()

    def print_header(self, message: str) -> None:
        """打印标题"""
        print("\n" + "=" * 60)
        print(f"  {message}")
        print("=" * 60 + "\n")

    def print_info(self, message: str) -> None:
        """打印信息"""
        print(f"[INFO] {message}")

    def print_success(self, message: str) -> None:
        """打印成功信息"""
        print(f"[SUCCESS] {message}")

    def print_error(self, message: str) -> None:
        """打印错误信息"""
        print(f"[ERROR] {message}")

    def print_warning(self, message: str) -> None:
        """打印警告信息"""
        print(f"[WARNING] {message}")

    def check_python_version(self) -> bool:
        """检查 Python 版本"""
        self.print_info(f"Python 版本: {sys.version}")

        if sys.version_info < (3, 7):
            self.print_error("需要 Python 3.7 或更高版本")
            return False

        self.print_success("Python 版本检查通过")
        return True

    def check_requirements_file(self) -> bool:
        """检查 requirements.txt 文件"""
        if not self.requirements_file.exists():
            self.print_error(f"requirements.txt 文件不存在: {self.requirements_file}")
            return False

        self.print_success(f"requirements.txt 文件已找到: {self.requirements_file}")
        return True

    def create_virtual_environment(self) -> bool:
        """创建虚拟环境"""
        self.print_info(f"创建虚拟环境: {self.venv_dir}")

        try:
            # 如果虚拟环境已存在，提示用户
            if self.venv_dir.exists():
                self.print_warning(f"虚拟环境已存在: {self.venv_dir}")
                response = input("是否删除并重新创建? (y/n): ").strip().lower()
                if response == "y":
                    import shutil
                    shutil.rmtree(self.venv_dir)
                    self.print_info("已删除旧虚拟环境")
                else:
                    self.print_info("使用现有虚拟环境")
                    return True

            # 创建虚拟环境
            subprocess.check_call(
                [self.python_executable, "-m", "venv", str(self.venv_dir)]
            )

            self.print_success(f"虚拟环境创建成功: {self.venv_dir}")
            return True

        except subprocess.CalledProcessError as e:
            self.print_error(f"创建虚拟环境失败: {str(e)}")
            return False
        except Exception as e:
            self.print_error(f"创建虚拟环境时出错: {str(e)}")
            return False

    def get_pip_executable(self) -> Path:
        """获取虚拟环境中的 pip 可执行文件路径"""
        if self.system == "Windows":
            return self.venv_dir / "Scripts" / "pip.exe"
        else:
            return self.venv_dir / "bin" / "pip"

    def get_python_executable(self) -> Path:
        """获取虚拟环境中的 Python 可执行文件路径"""
        if self.system == "Windows":
            return self.venv_dir / "Scripts" / "python.exe"
        else:
            return self.venv_dir / "bin" / "python"

    def upgrade_pip(self) -> bool:
        """升级 pip"""
        self.print_info("升级 pip...")

        pip_executable = self.get_pip_executable()

        try:
            subprocess.check_call(
                [str(pip_executable), "install", "--upgrade", "pip"]
            )

            self.print_success("pip 升级成功")
            return True

        except subprocess.CalledProcessError as e:
            self.print_warning(f"pip 升级失败: {str(e)}")
            # 不中断流程，继续安装依赖
            return True
        except Exception as e:
            self.print_warning(f"pip 升级时出错: {str(e)}")
            return True

    def install_dependencies(self) -> bool:
        """安装依赖"""
        self.print_info(f"安装依赖: {self.requirements_file}")

        pip_executable = self.get_pip_executable()

        try:
            subprocess.check_call(
                [
                    str(pip_executable),
                    "install",
                    "-r",
                    str(self.requirements_file),
                ]
            )

            self.print_success("依赖安装成功")
            return True

        except subprocess.CalledProcessError as e:
            self.print_error(f"依赖安装失败: {str(e)}")
            return False
        except Exception as e:
            self.print_error(f"依赖安装时出错: {str(e)}")
            return False

    def verify_installation(self) -> bool:
        """验证安装"""
        self.print_info("验证安装...")

        python_executable = self.get_python_executable()

        try:
            # 检查虚拟环境中的 Python 是否可用
            result = subprocess.run(
                [str(python_executable), "--version"],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                self.print_success(f"虚拟环境验证成功: {result.stdout.strip()}")
                return True
            else:
                self.print_error(f"虚拟环境验证失败: {result.stderr}")
                return False

        except Exception as e:
            self.print_error(f"验证安装时出错: {str(e)}")
            return False

    def print_activation_instructions(self) -> None:
        """打印激活虚拟环境的说明"""
        self.print_header("虚拟环境激活说明")

        if self.system == "Windows":
            activate_cmd = str(self.venv_dir / "Scripts" / "activate.bat")
            self.print_info(f"Windows 激活命令:")
            print(f"  {activate_cmd}\n")
        else:
            activate_cmd = str(self.venv_dir / "bin" / "activate")
            self.print_info(f"macOS/Linux 激活命令:")
            print(f"  source {activate_cmd}\n")

    def run_setup(self) -> bool:
        """运行完整的设置流程"""
        self.print_header("项目环境自动配置")

        self.print_info(f"操作系统: {self.system}")
        self.print_info(f"项目根目录: {self.project_root}")
        self.print_info(f"Python 可执行文件: {self.python_executable}")

        # 检查 Python 版本
        if not self.check_python_version():
            return False

        # 检查 requirements.txt
        if not self.check_requirements_file():
            return False

        # 创建虚拟环境
        if not self.create_virtual_environment():
            return False

        # 升级 pip
        if not self.upgrade_pip():
            return False

        # 安装依赖
        if not self.install_dependencies():
            return False

        # 验证安装
        if not self.verify_installation():
            return False

        # 打印激活说明
        self.print_activation_instructions()

        self.print_header("环境配置完成")
        self.print_success("所有步骤已完成！")
        self.print_info("请激活虚拟环境后开始使用项目")

        return True


def main():
    """主函数"""
    try:
        setup = EnvironmentSetup()
        success = setup.run_setup()

        if success:
            sys.exit(0)
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n[INFO] 用户中断了设置过程")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] 发生未预期的错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
