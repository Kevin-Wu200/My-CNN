"""
训练样本 API 接口模块
用于处理训练样本的上传、解压和验证
"""

import logging
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException, status, BackgroundTasks, Query
from fastapi.responses import JSONResponse

from backend.config.settings import (
    UPLOAD_DIR,
    TRAINING_SAMPLES_DIR,
    DETECTION_IMAGES_DIR,
    TEMP_DIR,
)
from backend.services.decompression import DecompressionService
from backend.services.validation import ValidationService
from backend.services.background_task_manager import get_task_manager
from backend.utils.file_path_manager import FilePathManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/training", tags=["training"])

# 初始化服务
decompression_service = DecompressionService(TEMP_DIR)
task_manager = get_task_manager()


@router.post("/upload-sample")
async def upload_training_sample(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    上传训练样本压缩包接口

    接收 ZIP 或 RAR 压缩包，包含：
    - 多个按时间顺序命名的遥感影像文件（1.jpg、2.png、3.tif 等，支持 jpg、jpeg、png、tif、tiff 格式）
    - 一个 GeoJSON 文件用于病害木点位标注

    Args:
        file: 上传的压缩文件

    Returns:
        包含处理结果的 JSON 响应
    """
    try:
        # 验证文件类型
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件名不能为空",
            )

        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in [".zip", ".rar"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的文件格式: {file_ext}，仅支持 .zip 和 .rar",
            )

        # 保存上传的文件
        # 步骤7: 统一文件路径来源 - 使用 FilePathManager 获取上传目录
        upload_path = FilePathManager.get_upload_dir() / file.filename
        FilePathManager.ensure_directory_exists(upload_path.parent)

        with open(upload_path, "wb") as f:
            content = await file.read()
            f.write(content)

        logger.info(f"文件上传成功: {upload_path}")

        # 解压文件
        success, message, extract_dir = decompression_service.decompress_file(
            str(upload_path)
        )

        if not success:
            logger.error(f"解压失败: {message}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message,
            )

        logger.info(f"文件解压成功: {extract_dir}")

        # 验证训练样本
        valid, validation_message, validation_result = (
            ValidationService.validate_training_sample(extract_dir)
        )

        if not valid:
            logger.error(f"验证失败: {validation_message}")
            # 清理临时文件
            decompression_service.cleanup_temp_dir(extract_dir)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation_message,
            )

        logger.info(f"验证成功: {validation_message}")

        # 将验证通过的文件移动到训练样本目录
        sample_name = upload_path.stem
        # 步骤7: 统一文件路径来源 - 使用 FilePathManager 获取训练样本目录
        sample_dir = FilePathManager.get_training_samples_dir() / sample_name
        FilePathManager.ensure_directory_exists(sample_dir)

        # 复制文件到训练样本目录
        import shutil

        for file_path in extract_dir.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(extract_dir)
                dest_path = sample_dir / relative_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, dest_path)

        # 清理临时文件
        decompression_service.cleanup_temp_dir(extract_dir)

        logger.info(f"训练样本已保存到: {sample_dir}")

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "message": "训练样本上传和验证成功",
                "sample_name": sample_name,
                "sample_path": str(sample_dir),
                "image_files": validation_result["image_files"],
                "geojson_file": validation_result["geojson_file"],
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理训练样本时出错: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理文件时出错: {str(e)}",
        )


@router.post("/upload-detection-images")
async def upload_detection_images(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    上传待检测影像接口

    接收单个遥感影像文件（支持 jpg、jpeg、png、tif、tiff 格式）
    不要求 GeoJSON 文件

    Args:
        file: 上传的影像文件

    Returns:
        包含处理结果的 JSON 响应
    """
    try:
        # 验证文件名
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件名不能为空",
            )

        file_ext = Path(file.filename).suffix.lower()
        supported_formats = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
        if file_ext not in supported_formats:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的文件格式: {file_ext}，仅支持 jpg、jpeg、png、tif、tiff",
            )

        # 创建检测影像目录（使用时间戳作为目录名）
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 步骤7: 统一文件路径来源 - 使用 FilePathManager 获取检测影像目录
        detection_dir = FilePathManager.get_detection_images_dir() / timestamp
        FilePathManager.ensure_directory_exists(detection_dir)

        # 保存上传的文件
        file_path = detection_dir / file.filename
        content = await file.read()

        # 验证文件大小（至少 1KB）
        if len(content) < 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件过小（可能损坏），文件大小必须至少 1KB",
            )

        with open(file_path, "wb") as f:
            f.write(content)

        logger.info(f"待检测影像已保存到: {file_path}")

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "message": "待检测影像上传成功",
                "detection_name": timestamp,
                "detection_path": str(detection_dir),
                "image_files": [str(file_path)],
                "filename": file.filename,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理待检测影像时出错: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理文件时出错: {str(e)}",
        )


@router.post("/start-training")
async def start_training(
    sample_path: str = Query(..., description="训练样本路径"),
    task_name: str = Query(..., description="训练任务名称"),
    background_tasks: BackgroundTasks = None,
) -> Dict[str, Any]:
    """
    启动训练任务（异步）

    Args:
        sample_path: 训练样本路径
        task_name: 训练任务名称
        background_tasks: FastAPI 后台任务

    Returns:
        包含任务ID的 JSON 响应
    """
    try:
        # 验证样本路径是否存在
        sample_dir = Path(sample_path)
        if not sample_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"训练样本路径不存在: {sample_path}",
            )

        # 创建任务
        task_id = task_manager.create_task("training")

        # 启动后台任务
        if background_tasks:
            background_tasks.add_task(
                _run_training_task,
                task_id,
                sample_path,
                task_name,
            )

        logger.info(f"训练任务已启动: {task_id}")

        return {
            "status": "started",
            "task_id": task_id,
            "message": "训练任务已启动，请使用任务ID查询进度",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动训练任务失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动训练任务失败: {str(e)}",
        )


def _run_training_task(
    task_id: str,
    sample_path: str,
    task_name: str,
) -> None:
    """
    后台执行训练任务

    Args:
        task_id: 任务ID
        sample_path: 训练样本路径
        task_name: 训练任务名称
    """
    try:
        # 标记任务为运行中
        task_manager.start_task(task_id)
        task_manager.update_progress(task_id, 10, "初始化训练任务")
        logger.info(f"[{task_id}] 训练任务已启动，样本路径: {sample_path}")

        # 这里应该调用实际的训练服务
        # 目前作为占位符实现
        task_manager.update_progress(task_id, 30, "加载训练数据中")
        logger.info(f"[{task_id}] 开始加载训练数据")

        # 模拟训练过程
        import time
        time.sleep(2)

        task_manager.update_progress(task_id, 60, "模型训练中")
        logger.info(f"[{task_id}] 开始模型训练")
        time.sleep(2)

        task_manager.update_progress(task_id, 90, "保存模型中")
        logger.info(f"[{task_id}] 开始保存模型")

        # 返回训练结果
        result_data = {
            "status": "success",
            "message": "训练任务完成",
            "task_name": task_name,
            "sample_path": sample_path,
            "model_path": f"{TRAINING_SAMPLES_DIR}/models/{task_id}.pth",
        }

        logger.info(f"[{task_id}] 训练任务完成")

        # 标记任务为完成
        task_manager.complete_task(task_id, result_data)

    except Exception as e:
        logger.error(f"[{task_id}] 训练任务执行失败: {str(e)}")
        task_manager.fail_task(task_id, f"训练任务执行失败: {str(e)}")
