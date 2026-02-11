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
