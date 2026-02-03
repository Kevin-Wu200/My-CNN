"""
日志工具模块
用于记录系统运行日志
"""

import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
from typing import Optional


class LoggerSetup:
    """日志设置工具类"""

    _loggers = {}

    @staticmethod
    def setup_logger(
        name: str,
        log_dir: Path = Path("./logs"),
        level: int = logging.INFO,
    ) -> logging.Logger:
        """
        设置日志记录器

        Args:
            name: 日志记录器名称
            log_dir: 日志目录
            level: 日志级别

        Returns:
            配置好的日志记录器
        """
        # 如果已经配置过，直接返回
        if name in LoggerSetup._loggers:
            return LoggerSetup._loggers[name]

        # 创建日志目录
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        # 创建日志记录器
        logger = logging.getLogger(name)
        logger.setLevel(level)

        # 创建日志格式
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # 文件处理器（每日轮转）
        log_file = log_dir / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=10,
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # 缓存日志记录器
        LoggerSetup._loggers[name] = logger

        return logger

    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """
        获取日志记录器

        Args:
            name: 日志记录器名称

        Returns:
            日志记录器
        """
        if name not in LoggerSetup._loggers:
            return LoggerSetup.setup_logger(name)

        return LoggerSetup._loggers[name]


# 初始化全局日志记录器
logger = LoggerSetup.setup_logger("system")
