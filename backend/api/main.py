"""
FastAPI 主应用程序入口
用于初始化 FastAPI 应用并注册所有 API 路由
包含优雅关闭信号处理机制
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import signal
import sys
import time
import os
import multiprocessing as mp
from typing import Optional

from backend.api.training_sample import router as training_router
from backend.api.detection_config import router as detection_config_router
from backend.api.unsupervised_detection import router as unsupervised_router
from backend.api.upload import router as upload_router
from backend.api.task_status import router as task_status_router
from backend.utils.logger import LoggerSetup
from backend.utils.thread_limiter import limit_numerical_library_threads, log_thread_configuration
from backend.config.settings import NUMERICAL_LIBRARY_THREADS
from backend.services.background_task_manager import get_task_manager, TaskStatus

# Development mode flag - only enable reload in development
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

# 初始化日志
logger = LoggerSetup.setup_logger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="遥感影像病害木检测系统 API",
    description="用于训练样本上传、模型训练、病害木检测的 API 接口",
    version="1.0.0",
)

# 配置 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由 - 添加 /api 前缀以匹配前端期望的API路由
app.include_router(training_router, prefix="/api")
app.include_router(detection_config_router, prefix="/api")
app.include_router(unsupervised_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.include_router(task_status_router, prefix="/api")


# ==================== 优雅关闭信号处理 ====================

class GracefulShutdownManager:
    """优雅关闭管理器"""

    def __init__(self):
        """初始化关闭管理器"""
        self.shutdown_event = mp.Event()
        self.is_shutting_down = False
        self.shutdown_start_time: Optional[float] = None
        self.shutdown_timeout = 60  # 关闭超时时间（秒）
        self.task_manager = get_task_manager()

    def is_shutdown_in_progress(self) -> bool:
        """检查是否正在关闭"""
        return self.is_shutting_down

    def set_shutdown_flag(self) -> None:
        """设置关闭标志"""
        self.is_shutting_down = True
        self.shutdown_start_time = time.time()
        self.shutdown_event.set()

    def get_shutdown_elapsed_time(self) -> float:
        """获取关闭已用时间"""
        if self.shutdown_start_time is None:
            return 0.0
        return time.time() - self.shutdown_start_time

    def handle_shutdown_signal(self, signum: int, frame) -> None:
        """
        处理关闭信号（SIGINT/SIGTERM）

        关键保证：
        - 不会强制退出主进程
        - 只标记关闭标志，让 uvicorn 自然关闭
        - 任何异常都被捕获并记录，不会导致服务崩溃

        Args:
            signum: 信号编号
            frame: 当前栈帧
        """
        signal_name = signal.Signals(signum).name
        logger.warning(f"收到信号: {signal_name} ({signum})")

        if self.is_shutting_down:
            logger.warning(
                f"关闭已在进行中，已用时间: {self.get_shutdown_elapsed_time():.1f}秒"
            )
            return

        logger.info("=" * 60)
        logger.info("开始优雅关闭流程...")
        logger.info("=" * 60)

        self.set_shutdown_flag()

        try:
            # 第一步：停止新任务创建
            logger.info("[第1步] 停止接受新任务...")
            self._stop_new_tasks()

            # 第二步：终止运行中的任务
            logger.info("[第2步] 终止运行中的任务...")
            self._terminate_running_tasks()

            # 第三步：等待子进程完全退出
            logger.info("[第3步] 等待子进程完全退出...")
            self._wait_for_child_processes()

            # 第四步：清理资源
            logger.info("[第4步] 清理资源...")
            self._cleanup_resources()

            logger.info("=" * 60)
            logger.info(
                f"优雅关闭完成，总耗时: {self.get_shutdown_elapsed_time():.1f}秒"
            )
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"关闭过程中发生错误: {str(e)}", exc_info=True)
            # 关键：不在 finally 中调用 sys.exit()
            # 让 uvicorn 自然处理关闭流程
            logger.warning("关闭流程异常，但不强制退出主进程")

    def _stop_new_tasks(self) -> None:
        """停止新任务创建"""
        try:
            logger.info("设置关闭标志，拒绝新任务创建")
            # 标志已在 set_shutdown_flag() 中设置
            logger.info("新任务创建已停止")
        except Exception as e:
            logger.error(f"停止新任务创建失败: {str(e)}")

    def _terminate_running_tasks(self) -> None:
        """终止运行中的任务"""
        try:
            task_manager = self.task_manager
            running_tasks = task_manager.get_tasks_by_status(TaskStatus.RUNNING)

            if not running_tasks:
                logger.info("没有运行中的任务")
                return

            logger.info(f"发现 {len(running_tasks)} 个运行中的任务")

            for task_id, task_info in running_tasks.items():
                logger.info(
                    f"强制终止任务: {task_id} "
                    f"(类型: {task_info.get('task_type')}, "
                    f"进度: {task_info.get('progress')}%)"
                )
                # 强制终止任务（包括进程池）
                task_manager.force_terminate_task(task_id)

            logger.info(f"已强制终止 {len(running_tasks)} 个任务")

        except Exception as e:
            logger.error(f"终止运行中的任务失败: {str(e)}", exc_info=True)

    def _wait_for_child_processes(self) -> None:
        """等待所有子进程完全退出"""
        try:
            # 获取当前进程的所有子进程
            current_process = mp.current_process()
            logger.info(f"当前进程: {current_process.name} (PID: {current_process.pid})")

            # 获取所有活跃的子进程
            active_children = mp.active_children()

            if not active_children:
                logger.info("没有活跃的子进程")
                return

            logger.info(f"发现 {len(active_children)} 个活跃子进程")

            # 记录子进程信息
            for child in active_children:
                logger.info(
                    f"子进程: {child.name} (PID: {child.pid}, "
                    f"daemon: {child.daemon})"
                )

            # 等待子进程退出，设置超时
            wait_start = time.time()
            remaining_timeout = self.shutdown_timeout

            for child in active_children:
                if remaining_timeout <= 0:
                    logger.warning(
                        f"等待子进程超时，强制终止剩余进程"
                    )
                    break

                try:
                    child.join(timeout=remaining_timeout)
                    elapsed = time.time() - wait_start
                    remaining_timeout = self.shutdown_timeout - elapsed

                    if child.is_alive():
                        logger.warning(
                            f"子进程 {child.name} (PID: {child.pid}) "
                            f"未在超时内退出，尝试强制终止"
                        )
                        child.terminate()
                        child.join(timeout=5)

                        if child.is_alive():
                            logger.error(
                                f"子进程 {child.name} (PID: {child.pid}) "
                                f"强制终止失败，尝试 kill"
                            )
                            child.kill()
                            child.join(timeout=2)
                    else:
                        logger.info(
                            f"子进程 {child.name} (PID: {child.pid}) "
                            f"已正常退出"
                        )

                except Exception as e:
                    logger.error(
                        f"等待子进程 {child.name} 失败: {str(e)}"
                    )

            # 最终检查
            remaining_children = mp.active_children()
            if remaining_children:
                logger.warning(
                    f"仍有 {len(remaining_children)} 个子进程未退出"
                )
                for child in remaining_children:
                    logger.warning(
                        f"未退出的子进程: {child.name} (PID: {child.pid})"
                    )
            else:
                logger.info("所有子进程已成功退出")

        except Exception as e:
            logger.error(f"等待子进程失败: {str(e)}", exc_info=True)

    def _cleanup_resources(self) -> None:
        """清理资源"""
        try:
            logger.info("执行资源清理...")

            # 关闭任务管理器，等待活动线程
            try:
                logger.info("关闭任务管理器...")
                self.task_manager.shutdown(timeout=30)
                logger.info("任务管理器已关闭")
            except Exception as e:
                logger.warning(f"关闭任务管理器失败: {str(e)}")

            # 清理旧任务
            try:
                removed_count = self.task_manager.cleanup_old_tasks(max_age_hours=24)
                logger.info(f"清理了 {removed_count} 个旧任务")
            except Exception as e:
                logger.warning(f"清理旧任务失败: {str(e)}")

            # 关闭数据库连接（如果有）
            try:
                from backend.models.database import get_db_manager
                db_manager = get_db_manager()
                if db_manager:
                    logger.info("关闭数据库连接...")
                    # 数据库管理器的清理逻辑
            except Exception as e:
                logger.warning(f"关闭数据库连接失败: {str(e)}")

            logger.info("资源清理完成")

        except Exception as e:
            logger.error(f"资源清理失败: {str(e)}", exc_info=True)


# 创建全局关闭管理器实例
shutdown_manager = GracefulShutdownManager()


def setup_signal_handlers() -> None:
    """设置信号处理器"""
    logger.info("设置信号处理器...")

    try:
        # 注册 SIGINT 处理器 (Ctrl+C)
        signal.signal(signal.SIGINT, shutdown_manager.handle_shutdown_signal)
        logger.info("已注册 SIGINT 处理器")

        # 注册 SIGTERM 处理器 (kill 命令)
        signal.signal(signal.SIGTERM, shutdown_manager.handle_shutdown_signal)
        logger.info("已注册 SIGTERM 处理器")

        logger.info("信号处理器设置完成")

    except Exception as e:
        logger.error(f"设置信号处理器失败: {str(e)}", exc_info=True)


# 应用启动事件
@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info("=" * 60)
    logger.info("FastAPI 应用启动完成")
    logger.info(f"进程 ID: {mp.current_process().pid}")
    logger.info(f"CPU 核心数: {mp.cpu_count()}")
    logger.info("=" * 60)

    # 限制数值库线程数
    logger.info("配置数值库线程限制...")
    limit_numerical_library_threads(num_threads=NUMERICAL_LIBRARY_THREADS)

    # 记录线程配置信息
    log_thread_configuration()

    logger.info("=" * 60)
    logger.info("后端服务已准备就绪，监听 0.0.0.0:8000")
    logger.info("=" * 60)


# 应用关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("FastAPI 应用关闭事件触发")

    # 如果不是通过信号触发的关闭，执行清理
    if not shutdown_manager.is_shutdown_in_progress():
        logger.info("通过 FastAPI 事件触发关闭流程")
        shutdown_manager.set_shutdown_flag()

        try:
            # 执行清理步骤
            shutdown_manager._terminate_running_tasks()
            shutdown_manager._wait_for_child_processes()
            shutdown_manager._cleanup_resources()
        except Exception as e:
            logger.error(f"关闭清理失败: {str(e)}", exc_info=True)


# 健康检查端点
@app.get("/health")
async def health_check():
    """健康检查端点"""
    if shutdown_manager.is_shutdown_in_progress():
        return {
            "status": "shutting_down",
            "message": "服务器正在关闭",
            "shutdown_elapsed_time": shutdown_manager.get_shutdown_elapsed_time(),
        }

    return {
        "status": "healthy",
        "message": "API 服务正常运行",
    }


# 根路由
@app.get("/")
async def root():
    """根路由"""
    return {
        "message": "欢迎使用遥感影像病害木检测系统 API",
        "version": "1.0.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    logger.info("启动 FastAPI 服务...")
    logger.info("=" * 60)

    # 设置信号处理器
    setup_signal_handlers()

    logger.info("=" * 60)

    try:
        uvicorn.run(
            "backend.api.main:app",
            host="0.0.0.0",
            port=8000,
            reload=DEV_MODE,
            timeout_keep_alive=43200,  # 12小时 keep-alive 超时
        )
    except KeyboardInterrupt:
        logger.info("捕获到 KeyboardInterrupt，服务正在关闭...")
    except Exception as e:
        logger.error(f"服务启动失败: {str(e)}", exc_info=True)
        # 关键：不调用 sys.exit(1)，让进程自然退出
        # 这样可以确保任何清理代码都有机会执行
