"""
资源监控模块
用于监控系统资源使用情况（CPU、内存、进程数、线程数）
"""

import psutil
import os
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ResourceMonitor:
    """资源监控类"""

    @staticmethod
    def get_process_count() -> int:
        """
        获取当前进程数

        Returns:
            当前系统进程数
        """
        try:
            return len(psutil.pids())
        except Exception as e:
            logger.warning(f"获取进程数失败: {str(e)}")
            return -1

    @staticmethod
    def get_thread_count() -> int:
        """
        获取当前线程数

        Returns:
            当前进程的线程数
        """
        try:
            process = psutil.Process(os.getpid())
            return process.num_threads()
        except Exception as e:
            logger.warning(f"获取线程数失败: {str(e)}")
            return -1

    @staticmethod
    def get_cpu_usage() -> float:
        """
        获取 CPU 使用率

        Returns:
            CPU 使用率（百分比，0-100）
        """
        try:
            return psutil.cpu_percent(interval=0.1)
        except Exception as e:
            logger.warning(f"获取 CPU 使用率失败: {str(e)}")
            return -1.0

    @staticmethod
    def get_memory_usage() -> Dict[str, Any]:
        """
        获取内存使用情况

        Returns:
            包含内存使用信息的字典
            {
                'total': 总内存（MB）,
                'used': 已用内存（MB）,
                'available': 可用内存（MB）,
                'percent': 内存使用率（%）,
                'process_rss': 当前进程 RSS 内存（MB）,
                'process_vms': 当前进程 VMS 内存（MB）
            }
        """
        try:
            # 系统内存
            virtual_memory = psutil.virtual_memory()

            # 当前进程内存
            process = psutil.Process(os.getpid())
            process_memory = process.memory_info()

            return {
                'total': virtual_memory.total / (1024 * 1024),  # 转换为 MB
                'used': virtual_memory.used / (1024 * 1024),
                'available': virtual_memory.available / (1024 * 1024),
                'percent': virtual_memory.percent,
                'process_rss': process_memory.rss / (1024 * 1024),  # RSS 内存
                'process_vms': process_memory.vms / (1024 * 1024),  # VMS 内存
            }
        except Exception as e:
            logger.warning(f"获取内存使用情况失败: {str(e)}")
            return {
                'total': -1,
                'used': -1,
                'available': -1,
                'percent': -1,
                'process_rss': -1,
                'process_vms': -1,
            }

    @staticmethod
    def log_resource_status(label: str = "资源状态") -> None:
        """
        记录当前资源状态

        Args:
            label: 日志标签
        """
        try:
            process_count = ResourceMonitor.get_process_count()
            thread_count = ResourceMonitor.get_thread_count()
            cpu_usage = ResourceMonitor.get_cpu_usage()
            memory_info = ResourceMonitor.get_memory_usage()

            logger.info(
                f"[{label}] 进程数={process_count}, 线程数={thread_count}, "
                f"CPU使用率={cpu_usage:.1f}%, "
                f"系统内存={memory_info['used']:.1f}MB/{memory_info['total']:.1f}MB "
                f"({memory_info['percent']:.1f}%), "
                f"进程内存=RSS {memory_info['process_rss']:.1f}MB / VMS {memory_info['process_vms']:.1f}MB"
            )
        except Exception as e:
            logger.error(f"记录资源状态失败: {str(e)}")

    @staticmethod
    def get_resource_snapshot() -> Dict[str, Any]:
        """
        获取资源快照

        Returns:
            包含完整资源信息的字典
        """
        try:
            memory_info = ResourceMonitor.get_memory_usage()

            return {
                'timestamp': datetime.now().isoformat(),
                'process_count': ResourceMonitor.get_process_count(),
                'thread_count': ResourceMonitor.get_thread_count(),
                'cpu_usage': ResourceMonitor.get_cpu_usage(),
                'memory': memory_info,
            }
        except Exception as e:
            logger.error(f"获取资源快照失败: {str(e)}")
            return {}

    @staticmethod
    def log_process_lifecycle(event: str, process_id: int = None) -> None:
        """
        记录进程生命周期事件

        Args:
            event: 事件类型 ("start", "end", "error")
            process_id: 进程 ID（如果为 None，使用当前进程）
        """
        if process_id is None:
            process_id = os.getpid()

        try:
            if event == "start":
                logger.info(f"进程启动: PID={process_id}")
            elif event == "end":
                logger.info(f"进程结束: PID={process_id}")
            elif event == "error":
                logger.error(f"进程异常: PID={process_id}")
            else:
                logger.debug(f"进程事件: {event}, PID={process_id}")
        except Exception as e:
            logger.error(f"记录进程生命周期失败: {str(e)}")

    @staticmethod
    def log_thread_lifecycle(event: str, thread_name: str = None) -> None:
        """
        记录线程生命周期事件

        Args:
            event: 事件类型 ("start", "end", "error")
            thread_name: 线程名称
        """
        import threading

        if thread_name is None:
            thread_name = threading.current_thread().name

        try:
            if event == "start":
                logger.info(f"线程启动: {thread_name}")
            elif event == "end":
                logger.info(f"线程结束: {thread_name}")
            elif event == "error":
                logger.error(f"线程异常: {thread_name}")
            else:
                logger.debug(f"线程事件: {event}, {thread_name}")
        except Exception as e:
            logger.error(f"记录线程生命周期失败: {str(e)}")
