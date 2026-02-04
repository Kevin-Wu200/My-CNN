"""
日志工具模块
用于记录系统运行日志
支持进程/线程生命周期、资源监控、任务跟踪等详细日志记录
"""

import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
from typing import Optional
import os


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

        # 创建日志格式（增强版本，包含进程ID和线程ID）
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - [PID:%(process)d] [TID:%(thread)d] - %(levelname)s - %(message)s",
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

    @staticmethod
    def log_process_start(process_name: str, logger_obj: logging.Logger = None) -> None:
        """
        记录进程启动事件

        Args:
            process_name: 进程名称
            logger_obj: 日志记录器（如果为 None，使用全局日志记录器）
        """
        if logger_obj is None:
            logger_obj = logger

        logger_obj.info(
            f"进程启动: {process_name}, PID={os.getpid()}"
        )

    @staticmethod
    def log_process_end(process_name: str, logger_obj: logging.Logger = None) -> None:
        """
        记录进程结束事件

        Args:
            process_name: 进程名称
            logger_obj: 日志记录器（如果为 None，使用全局日志记录器）
        """
        if logger_obj is None:
            logger_obj = logger

        logger_obj.info(
            f"进程结束: {process_name}, PID={os.getpid()}"
        )

    @staticmethod
    def log_subprocess_start(subprocess_name: str, subprocess_pid: int, logger_obj: logging.Logger = None) -> None:
        """
        记录子进程启动事件

        Args:
            subprocess_name: 子进程名称
            subprocess_pid: 子进程 ID
            logger_obj: 日志记录器（如果为 None，使用全局日志记录器）
        """
        if logger_obj is None:
            logger_obj = logger

        logger_obj.info(
            f"子进程启动: {subprocess_name}, 子进程PID={subprocess_pid}, 父进程PID={os.getpid()}"
        )

    @staticmethod
    def log_subprocess_exit(subprocess_name: str, subprocess_pid: int, exit_code: int = None, logger_obj: logging.Logger = None) -> None:
        """
        记录子进程退出事件

        Args:
            subprocess_name: 子进程名称
            subprocess_pid: 子进程 ID
            exit_code: 退出码
            logger_obj: 日志记录器（如果为 None，使用全局日志记录器）
        """
        if logger_obj is None:
            logger_obj = logger

        if exit_code is not None:
            logger_obj.info(
                f"子进程退出: {subprocess_name}, 子进程PID={subprocess_pid}, 退出码={exit_code}"
            )
        else:
            logger_obj.info(
                f"子进程退出: {subprocess_name}, 子进程PID={subprocess_pid}"
            )

    @staticmethod
    def log_task_start(task_id: str, task_name: str, logger_obj: logging.Logger = None) -> None:
        """
        记录任务开始事件

        Args:
            task_id: 任务ID
            task_name: 任务名称
            logger_obj: 日志记录器（如果为 None，使用全局日志记录器）
        """
        if logger_obj is None:
            logger_obj = logger

        logger_obj.info(
            f"[{task_id}] 任务开始: {task_name}"
        )

    @staticmethod
    def log_task_end(task_id: str, task_name: str, success: bool = True, logger_obj: logging.Logger = None) -> None:
        """
        记录任务结束事件

        Args:
            task_id: 任务ID
            task_name: 任务名称
            success: 任务是否成功
            logger_obj: 日志记录器（如果为 None，使用全局日志记录器）
        """
        if logger_obj is None:
            logger_obj = logger

        status = "成功" if success else "失败"
        logger_obj.info(
            f"[{task_id}] 任务结束: {task_name}, 状态={status}"
        )


# 初始化全局日志记录器
logger = LoggerSetup.setup_logger("system")
