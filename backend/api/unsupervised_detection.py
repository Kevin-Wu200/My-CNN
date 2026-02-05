"""
无监督病害木检测 API 接口模块
"""

import logging
import uuid
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import JSONResponse
import numpy as np

from backend.config.settings import (
    UPLOAD_DIR,
    DETECTION_IMAGES_DIR,
    TEMP_DIR,
)
from backend.utils.image_reader import ImageReader
from backend.utils.resource_monitor import ResourceMonitor
from backend.services.unsupervised_detection import UnsupervisedDiseaseDetectionService
from backend.services.background_task_manager import get_task_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/unsupervised", tags=["unsupervised_detection"])

# 初始化服务
image_reader = ImageReader()
detection_service = UnsupervisedDiseaseDetectionService()
task_manager = get_task_manager()


@router.post("/upload-image")
async def upload_detection_image(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    上传待检测影像接口

    接收遥感影像文件（jpg、jpeg、png、tif、tiff 格式）

    Args:
        file: 上传的影像文件

    Returns:
        包含处理结果的 JSON 响应
    """
    try:
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件名不能为空",
            )

        # 验证文件类型
        allowed_extensions = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
        file_ext = Path(file.filename).suffix.lower()

        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的文件格式: {file_ext}，支持格式: {allowed_extensions}",
            )

        # 保存上传的文件
        upload_dir = Path(DETECTION_IMAGES_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        logger.info(f"影像文件上传成功: {file_path}")

        return {
            "status": "success",
            "message": "影像文件上传成功",
            "filename": file.filename,
            "file_path": str(file_path),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"影像文件上传失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"影像文件上传失败: {str(e)}",
        )


@router.post("/detect")
async def detect_disease(
    background_tasks: BackgroundTasks,
    image_path: str = Query(..., description="影像文件路径"),
    n_clusters: int = Query(4, ge=2, le=10, description="K-means 聚类类别数"),
    min_area: int = Query(50, ge=10, description="最小斑块面积阈值"),
) -> Dict[str, Any]:
    """
    启动无监督病害木检测任务（异步）

    基于光谱、纹理和空间特征的传统非监督分类方法

    Args:
        image_path: 影像文件路径
        n_clusters: K-means 聚类类别数（推荐 3-6）
        min_area: 最小斑块面积阈值
        background_tasks: FastAPI 后台任务

    Returns:
        包含任务ID的 JSON 响应
    """
    try:
        logger.info(f"[API] 收到无监督检测请求: image_path={image_path}, n_clusters={n_clusters}, min_area={min_area}")

        # 验证文件是否存在
        file_path = Path(image_path)
        if not file_path.exists():
            logger.warning(f"[API] 影像文件不存在: {image_path}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"影像文件不存在: {image_path}",
            )

        # 预创建任务ID（用于返回给客户端）
        task_id = str(uuid.uuid4())
        logger.info(f"[API] 创建任务ID: {task_id}")

        # 启动后台任务（任务创建移到后台函数内部）
        background_tasks.add_task(
            _run_unsupervised_detection_safe,
            task_id,
            str(file_path),
            n_clusters,
            min_area,
        )

        logger.info(f"[API] 无监督检测任务已提交到后台: {task_id}")

        return {
            "status": "started",
            "task_id": task_id,
            "message": "无监督病害木检测任务已启动，请使用任务ID查询进度",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] 启动检测任务失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动检测任务失败: {str(e)}",
        )


@router.get("/task-status/{task_id}")
async def get_detection_task_status(task_id: str) -> Dict[str, Any]:
    """
    查询无监督检测任务状态

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


def _run_unsupervised_detection_safe(
    task_id: str, image_path: str, n_clusters: int, min_area: int
) -> None:
    """
    安全包装器：确保任务创建和异常处理

    关键保证：
    - 任何异常都被捕获，不会导致服务进程退出
    - 任务状态始终被正确更新
    - 后端 Web 服务生命周期独立于单次任务

    Args:
        task_id: 任务ID
        image_path: 影像文件路径
        n_clusters: K-means 聚类类别数
        min_area: 最小斑块面积阈值
    """
    try:
        logger.info(f"[后台任务] 开始执行任务: {task_id}")

        # 在后台线程中创建任务，使用指定的 task_id（确保任务ID一致）
        task_manager.create_task("unsupervised_detection", task_id=task_id)
        logger.info(f"[后台任务] 任务已创建: {task_id}")

        # 立即标记为运行中
        task_manager.start_task(task_id)
        logger.info(f"[后台任务] 任务已标记为运行中: {task_id}")

        # 执行实际任务
        _run_unsupervised_detection(task_id, image_path, n_clusters, min_area)
        logger.info(f"[后台任务] 任务执行完成: {task_id}")

    except Exception as e:
        # 捕获所有异常，确保任务状态被正确更新
        # 关键：这里的异常不会导致服务进程退出
        logger.error(f"[后台任务] 任务执行异常: {task_id}, 错误: {str(e)}", exc_info=True)

        # 如果任务已创建，标记为失败
        if task_id in task_manager.tasks:
            task_manager.fail_task(task_id, f"任务执行异常: {str(e)}")
            logger.info(f"[后台任务] 任务已标记为失败: {task_id}")
        else:
            # 如果任务未创建，创建并标记为失败
            try:
                task_manager.create_task("unsupervised_detection", task_id=task_id)
                task_manager.fail_task(task_id, f"任务初始化失败: {str(e)}")
                logger.info(f"[后台任务] 任务已创建并标记为失败: {task_id}")
            except Exception as create_error:
                logger.error(f"[后台任务] 创建失败任务记录失败: {task_id}, 错误: {str(create_error)}", exc_info=True)


def _run_unsupervised_detection(
    task_id: str, image_path: str, n_clusters: int, min_area: int
) -> None:
    """
    后台执行无监督检测任务

    Args:
        task_id: 任务ID
        image_path: 影像文件路径
        n_clusters: K-means 聚类类别数
        min_area: 最小斑块面积阈值
    """
    try:
        # 标记任务为运行中
        logger.info(f"[{task_id}] 后台任务已启动")
        ResourceMonitor.log_resource_status(f"后台任务启动 [{task_id}]")

        # 第五步：在检测开始前增加文件存在性检查
        logger.info(f"[{task_id}] 开始文件就绪检查")
        file_path = Path(image_path)

        # 检查文件是否存在
        if not file_path.exists():
            error_msg = f"文件不存在: {image_path}"
            logger.error(f"[{task_id}] {error_msg}")
            task_manager.fail_task(task_id, error_msg)
            return

        logger.info(f"[{task_id}] 文件存在检查通过")

        # 检查文件大小是否大于 0
        file_size = file_path.stat().st_size
        if file_size <= 0:
            error_msg = f"文件大小无效: {file_size}"
            logger.error(f"[{task_id}] {error_msg}")
            task_manager.fail_task(task_id, error_msg)
            return

        logger.info(f"[{task_id}] 文件大小检查通过: {file_size} bytes")

        # 检查文件是否可读
        try:
            with open(file_path, "rb") as test_file:
                test_file.read(1)
            logger.info(f"[{task_id}] 文件可读性检查通过")
        except Exception as read_error:
            error_msg = f"文件不可读: {str(read_error)}"
            logger.error(f"[{task_id}] {error_msg}")
            task_manager.fail_task(task_id, error_msg)
            return

        logger.info(f"[{task_id}] 文件就绪检查完成，开始读取影像")

        task_manager.update_progress(task_id, 10, "读取影像中")
        logger.info(f"[{task_id}] 开始读取影像")

        # 读取影像
        logger.debug(f"[{task_id}] 读取影像: {image_path}")
        success, image_data, msg = image_reader.read_image(image_path)
        if not success:
            logger.error(f"[{task_id}] 影像读取失败: {msg}")
            task_manager.fail_task(task_id, f"影像读取失败: {msg}")
            return

        logger.info(f"[{task_id}] 影像读取成功，尺寸: {image_data.shape}")
        ResourceMonitor.log_resource_status(f"影像读取完成 [{task_id}]")
        task_manager.update_progress(task_id, 30, "执行检测中")

        # 执行无监督检测，传递任务管理器用于进度跟踪
        logger.info(f"[{task_id}] 开始执行无监督检测")
        success, result, msg = detection_service.detect(
            image_data,
            n_clusters=n_clusters,
            min_area=min_area,
            task_manager=task_manager,
            task_id=task_id,
        )

        if not success:
            logger.error(f"[{task_id}] 检测失败: {msg}")
            ResourceMonitor.log_resource_status(f"检测失败 [{task_id}]")
            task_manager.fail_task(task_id, f"检测失败: {msg}")
            return

        logger.info(f"[{task_id}] 检测完成，开始处理结果")
        ResourceMonitor.log_resource_status(f"检测完成，处理结果 [{task_id}]")
        task_manager.update_progress(task_id, 90, "处理结果中")

        # 保存检测结果
        result_data = {
            "status": "success",
            "message": "无监督病害木检测完成",
            "image_path": image_path,
            "image_shape": image_data.shape,
            "n_clusters": result["n_clusters"],
            "n_candidates": result["n_candidates"],
            "method": result["method"],
            "description": result["description"],
            "center_points": result["center_points"],
            "note": "该结果基于传统非监督分类方法，不是最终病害判定，适用于无标注或样本不足场景",
        }

        logger.info(f"[{task_id}] 检测完成，发现 {result['n_candidates']} 个病害木候选区域")

        # 标记任务为完成
        task_manager.complete_task(task_id, result_data)
        logger.info(f"[{task_id}] 后台任务已完成")
        ResourceMonitor.log_resource_status(f"后台任务完成 [{task_id}]")

    except Exception as e:
        logger.error(f"[{task_id}] 检测任务执行失败: {str(e)}")
        ResourceMonitor.log_resource_status(f"后台任务异常 [{task_id}]")
        task_manager.fail_task(task_id, f"检测任务执行失败: {str(e)}")


@router.get("/method-info")
async def get_method_info() -> Dict[str, Any]:
    """
    获取无监督检测方法说明接口

    Returns:
        方法说明信息
    """
    return {
        "method": "传统非监督分类方法",
        "description": "基于光谱、纹理和空间特征的无监督病害木检测",
        "steps": [
            {
                "step": 1,
                "name": "影像读取与标准化处理",
                "description": "读取遥感影像，进行浮点型转换和波段归一化",
            },
            {
                "step": 2,
                "name": "像元级特征构建",
                "description": "构建光谱特征（RGB、波段比值、归一化差异）和纹理特征（GLCM）",
            },
            {
                "step": 3,
                "name": "特征标准化",
                "description": "对特征矩阵进行零均值、单位方差标准化",
            },
            {
                "step": 4,
                "name": "非监督聚类",
                "description": "使用 K-means 聚类进行特征空间分组",
            },
            {
                "step": 5,
                "name": "病害木候选类别判定",
                "description": "基于光谱和纹理特征判定病害木候选类别",
            },
            {
                "step": 6,
                "name": "空间后处理",
                "description": "连通域分析、去除小斑块、计算几何中心",
            },
            {
                "step": 7,
                "name": "结果输出",
                "description": "输出病害木候选区域栅格图和中心点位",
            },
        ],
        "disease_mechanism": {
            "description": "松材线虫病害机理",
            "symptoms": [
                "针叶失水、叶绿素下降",
                "红波段反射增强、绿波段反射减弱",
                "树冠结构破碎、分布不均",
                "局部纹理更加粗糙",
            ],
        },
        "parameters": {
            "n_clusters": {
                "description": "K-means 聚类类别数",
                "recommended_range": [3, 6],
                "default": 4,
            },
            "min_area": {
                "description": "最小斑块面积阈值（像元数）",
                "recommended_range": [30, 100],
                "default": 50,
            },
        },
        "limitations": [
            "不使用深度学习模型",
            "不依赖人工标注",
            "适用于无标注或样本不足场景",
            "结果为候选区域，不是最终病害判定",
            "需要用户进行人工验证和修正",
        ],
    }
