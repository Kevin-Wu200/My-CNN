"""
错误处理工具模块
用于统一处理系统异常
"""

import traceback
from typing import Optional, Callable, Any
import logging

logger = logging.getLogger(__name__)


class ErrorHandler:
    """错误处理工具类"""

    @staticmethod
    def handle_exception(
        exception: Exception,
        context: str = "",
        logger_instance: Optional[logging.Logger] = None,
    ) -> str:
        """
        处理异常并记录日志

        Args:
            exception: 异常对象
            context: 错误上下文描述
            logger_instance: 日志记录器实例

        Returns:
            错误信息字符串
        """
        if logger_instance is None:
            logger_instance = logger

        # 获取异常堆栈跟踪
        error_traceback = traceback.format_exc()

        # 构建错误信息
        error_message = f"异常发生: {type(exception).__name__}"
        if context:
            error_message += f" (上下文: {context})"
        error_message += f"\n详情: {str(exception)}"

        # 记录错误
        logger_instance.error(error_message)
        logger_instance.debug(error_traceback)

        return error_message

    @staticmethod
    def safe_execute(
        func: Callable,
        *args,
        default_return: Any = None,
        error_context: str = "",
        **kwargs,
    ) -> Any:
        """
        安全执行函数，捕获异常

        Args:
            func: 要执行的函数
            *args: 位置参数
            default_return: 异常时的默认返回值
            error_context: 错误上下文
            **kwargs: 关键字参数

        Returns:
            函数返回值或默认值
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            ErrorHandler.handle_exception(e, error_context)
            return default_return

    @staticmethod
    def validate_input(
        value: Any,
        expected_type: type,
        param_name: str = "parameter",
    ) -> bool:
        """
        验证输入参数类型

        Args:
            value: 要验证的值
            expected_type: 期望的类型
            param_name: 参数名称

        Returns:
            验证是否通过
        """
        if not isinstance(value, expected_type):
            error_msg = (
                f"参数类型错误: {param_name} 应为 {expected_type.__name__}, "
                f"但收到 {type(value).__name__}"
            )
            logger.error(error_msg)
            return False

        return True

    @staticmethod
    def validate_file_exists(file_path: str, param_name: str = "file") -> bool:
        """
        验证文件是否存在

        Args:
            file_path: 文件路径
            param_name: 参数名称

        Returns:
            文件是否存在
        """
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            error_msg = f"{param_name} 不存在: {file_path}"
            logger.error(error_msg)
            return False

        return True

    @staticmethod
    def validate_directory_exists(
        dir_path: str, param_name: str = "directory"
    ) -> bool:
        """
        验证目录是否存在

        Args:
            dir_path: 目录路径
            param_name: 参数名称

        Returns:
            目录是否存在
        """
        from pathlib import Path

        path = Path(dir_path)
        if not path.is_dir():
            error_msg = f"{param_name} 不是有效的目录: {dir_path}"
            logger.error(error_msg)
            return False

        return True
