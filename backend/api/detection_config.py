"""
检测流程 API 接口模块
用于处理检测流程中的模型配置选择和检测任务管理
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, status, Query

from backend.config.settings import DATABASE_PATH
from backend.models.database import DatabaseManager, TrainingTask

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/detection", tags=["detection"])

# 初始化数据库管理器（使用全局单例避免重复初始化）
_db_manager = None

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
