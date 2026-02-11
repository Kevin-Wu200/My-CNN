"""
任务状态查询 API 接口模块
用于查询后台任务的执行状态
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status

from backend.services.background_task_manager import get_task_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["task_management"])

# 获取全局任务管理器
task_manager = get_task_manager()


@router.get("/status/{task_id}")
async def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    查询任务状态

    Args:
        task_id: 任务ID

    Returns:
        任务状态信息
    """
    task = task_manager.get_task_status(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务不存在: {task_id}",
        )

    return task


@router.get("/all")
async def get_all_tasks() -> Dict[str, Any]:
    """
    获取所有任务

    Returns:
        所有任务的字典
    """
    tasks = task_manager.get_all_tasks()
    return {
        "total": len(tasks),
        "tasks": tasks,
    }


@router.get("/by-status/{status}")
async def get_tasks_by_status(status: str) -> Dict[str, Any]:
    """
    按状态获取任务

    Args:
        status: 任务状态（pending, running, completed, failed）

    Returns:
        符合条件的任务字典
    """
    from backend.services.background_task_manager import TaskStatus

    try:
        task_status = TaskStatus(status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的任务状态: {status}，有效值: pending, running, completed, failed",
        )

    tasks = task_manager.get_tasks_by_status(task_status)
    return {
        "status": status,
        "total": len(tasks),
        "tasks": tasks,
    }


@router.post("/stop/{task_id}")
async def stop_task(task_id: str) -> Dict[str, Any]:
    """
    停止正在运行的任务

    Args:
        task_id: 任务ID

    Returns:
        停止结果
    """
    # 检查任务是否存在
    task = task_manager.get_task_status(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务不存在: {task_id}",
        )

    # 检查任务状态
    if task["status"] != "running":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"任务未在运行中，当前状态: {task['status']}",
        )

    try:
        # 设置停止标志
        task_manager.set_stop_flag(task_id)
        logger.info(f"已设置任务停止标志: {task_id}")

        # 强制终止任务
        task_manager.force_terminate_task(task_id)
        logger.info(f"已强制终止任务: {task_id}")

        return {
            "status": "stopped",
            "task_id": task_id,
            "message": "任务已终止",
        }
    except Exception as e:
        logger.error(f"停止任务失败: {task_id}, 错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"停止任务失败: {str(e)}",
        )
