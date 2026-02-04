"""
检测流程 API 接口模块
用于处理检测流程中的模型配置选择和检测任务管理
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, status, Query, BackgroundTasks

from backend.config.settings import DATABASE_PATH
from backend.models.database import DatabaseManager, TrainingTask
from backend.services.background_task_manager import get_task_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/detection", tags=["detection"])

# 初始化数据库管理器（使用全局单例避免重复初始化）
_db_manager = None
task_manager = get_task_manager()

def get_db_manager():
    """获取数据库管理器单例"""
    global _db_manager
    if _db_manager is None:
        try:
            _db_manager = DatabaseManager(str(DATABASE_PATH))
        except Exception as e:
            logger.warning(f"数据库初始化警告: {str(e)}")
            # 如果表已存在，继续使用
            _db_manager = DatabaseManager(str(DATABASE_PATH))
    return _db_manager


@router.get("/model-configs")
async def get_model_configs() -> Dict[str, Any]:
    """
    获取所有已完成的训练任务的模型配置接口

    Returns:
        包含模型配置列表的 JSON 响应
    """
    try:
        db_manager = get_db_manager()
        session = db_manager.get_session()

        # 查询所有已完成的训练任务
        completed_tasks = session.query(TrainingTask).filter(
            TrainingTask.status == "completed"
        ).all()

        session.close()

        if not completed_tasks:
            return {
                "status": "success",
                "message": "暂无已完成的训练任务",
                "configs": [],
            }

        # 构建配置列表
        configs = []
        for task in completed_tasks:
            try:
                model_config = json.loads(task.model_config)
                configs.append({
                    "id": task.id,
                    "task_name": task.task_name,
                    "config": model_config,
                    "model_path": task.model_path,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                })
            except json.JSONDecodeError:
                logger.warning(f"无法解析任务 {task.id} 的模型配置")
                continue

        logger.info(f"获取 {len(configs)} 个模型配置")

        return {
            "status": "success",
            "message": f"获取 {len(configs)} 个模型配置",
            "configs": configs,
        }

    except Exception as e:
        logger.error(f"获取模型配置失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取模型配置失败: {str(e)}",
        )


@router.get("/model-config/{task_id}")
async def get_model_config(task_id: int) -> Dict[str, Any]:
    """
    获取指定训练任务的模型配置接口

    Args:
        task_id: 训练任务 ID

    Returns:
        包含模型配置的 JSON 响应
    """
    try:
        db_manager = get_db_manager()
        session = db_manager.get_session()

        # 查询指定的训练任务
        task = session.query(TrainingTask).filter(
            TrainingTask.id == task_id,
            TrainingTask.status == "completed"
        ).first()

        session.close()

        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到任务 ID {task_id} 或任务未完成",
            )

        try:
            model_config = json.loads(task.model_config)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="模型配置格式错误",
            )

        logger.info(f"获取任务 {task_id} 的模型配置")

        return {
            "status": "success",
            "message": "获取模型配置成功",
            "id": task.id,
            "task_name": task.task_name,
            "config": model_config,
            "model_path": task.model_path,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取模型配置失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取模型配置失败: {str(e)}",
        )


@router.post("/start-detection")
async def start_detection(
    image_paths: List[str] = Query(..., description="待检测影像文件路径列表"),
    model_config_id: int = Query(..., description="模型配置ID"),
    temporal_type: str = Query("single", description="时间类型: single 或 temporal"),
    background_tasks: BackgroundTasks = None,
) -> Dict[str, Any]:
    """
    启动检测任务（异步）

    Args:
        image_paths: 待检测影像文件路径列表
        model_config_id: 使用的模型配置ID
        temporal_type: 时间类型（single 或 temporal）
        background_tasks: FastAPI 后台任务

    Returns:
        包含任务ID的 JSON 响应
    """
    try:
        # 验证模型配置是否存在
        db_manager = get_db_manager()
        session = db_manager.get_session()

        model_task = session.query(TrainingTask).filter(
            TrainingTask.id == model_config_id,
            TrainingTask.status == "completed"
        ).first()

        session.close()

        if not model_task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"模型配置不存在或未完成: {model_config_id}",
            )

        # 验证影像文件是否存在
        for image_path in image_paths:
            if not Path(image_path).exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"影像文件不存在: {image_path}",
                )

        # 创建任务
        task_id = task_manager.create_task("detection")

        # 启动后台任务
        if background_tasks:
            background_tasks.add_task(
                _run_detection_task,
                task_id,
                image_paths,
                model_config_id,
                temporal_type,
            )

        logger.info(f"检测任务已启动: {task_id}")

        return {
            "status": "started",
            "task_id": task_id,
            "message": "检测任务已启动，请使用任务ID查询进度",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动检测任务失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动检测任务失败: {str(e)}",
        )


def _run_detection_task(
    task_id: str,
    image_paths: List[str],
    model_config_id: int,
    temporal_type: str,
) -> None:
    """
    后台执行检测任务

    Args:
        task_id: 任务ID
        image_paths: 影像文件路径列表
        model_config_id: 模型配置ID
        temporal_type: 时间类型
    """
    try:
        # 标记任务为运行中
        task_manager.start_task(task_id)
        task_manager.update_progress(task_id, 10, "初始化检测任务")

        # 这里应该调用实际的检测服务
        # 目前作为占位符实现
        task_manager.update_progress(task_id, 50, "执行检测中")

        # 模拟检测过程
        import time
        time.sleep(2)

        task_manager.update_progress(task_id, 90, "处理结果中")

        # 返回检测结果
        result_data = {
            "status": "success",
            "message": "检测任务完成",
            "image_count": len(image_paths),
            "model_config_id": model_config_id,
            "temporal_type": temporal_type,
            "detection_results": [],
        }

        logger.info(f"检测任务完成: {task_id}")

        # 标记任务为完成
        task_manager.complete_task(task_id, result_data)

    except Exception as e:
        logger.error(f"检测任务执行失败: {str(e)}")
        task_manager.fail_task(task_id, f"检测任务执行失败: {str(e)}")
