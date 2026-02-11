"""
用户认证API模块
提供用户登录、用户信息查询和历史任务查询接口
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

from backend.models.database import get_db_manager
from backend.services.user_management import UserManagementService

logger = logging.getLogger(__name__)

router = APIRouter()

# 初始化服务
db_manager = get_db_manager()
user_service = UserManagementService(db_manager)


class LoginRequest(BaseModel):
    """登录请求模型"""
    phone: str


class LoginResponse(BaseModel):
    """登录响应模型"""
    success: bool
    data: Optional[dict] = None
    message: str


@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    用户登录接口

    Args:
        request: 登录请求，包含手机号

    Returns:
        登录结果，包含用户ID和手机号
    """
    try:
        success, user_id, message = user_service.login_user(request.phone)

        if success:
            return LoginResponse(
                success=True,
                data={"user_id": user_id, "phone": request.phone},
                message=message
            )
        else:
            return LoginResponse(
                success=False,
                message=message
            )
    except Exception as e:
        logger.error(f"登录接口异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"登录失败: {str(e)}")


@router.get("/auth/user/{user_id}")
async def get_user_info(user_id: int):
    """
    获取用户信息接口

    Args:
        user_id: 用户ID

    Returns:
        用户信息
    """
    try:
        success, user_info, message = user_service.get_user_info(user_id)

        if success:
            return {
                "success": True,
                "data": user_info,
                "message": message
            }
        else:
            return {
                "success": False,
                "message": message
            }
    except Exception as e:
        logger.error(f"获取用户信息异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取用户信息失败: {str(e)}")


@router.get("/history/training/{user_id}")
async def get_training_history(user_id: int):
    """
    获取训练历史接口

    Args:
        user_id: 用户ID

    Returns:
        训练任务列表
    """
    try:
        success, task_list, message = user_service.get_training_history(user_id)

        if success:
            return {
                "success": True,
                "data": task_list,
                "message": message
            }
        else:
            return {
                "success": False,
                "message": message
            }
    except Exception as e:
        logger.error(f"获取训练历史异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取训练历史失败: {str(e)}")


@router.get("/history/detection/{user_id}")
async def get_detection_history(user_id: int):
    """
    获取检测历史接口

    Args:
        user_id: 用户ID

    Returns:
        检测任务列表
    """
    try:
        success, task_list, message = user_service.get_detection_history(user_id)

        if success:
            return {
                "success": True,
                "data": task_list,
                "message": message
            }
        else:
            return {
                "success": False,
                "message": message
            }
    except Exception as e:
        logger.error(f"获取检测历史异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取检测历史失败: {str(e)}")
