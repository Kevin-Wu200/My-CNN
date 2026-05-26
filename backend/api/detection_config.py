"""
检测流程 API 接口模块
用于处理检测流程中的模型配置选择和检测任务管理
"""

import logging
import json
import torch
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

    集成 DiseaseTreeDetectionService，实现真实的推理逻辑。
    推理过程强制开启瓦片模式，以支持 4GB 量级的大图检测。

    Args:
        task_id: 任务ID
        image_paths: 影像文件路径列表
        model_config_id: 模型配置ID
        temporal_type: 时间类型
    """
    try:
        import json
        from pathlib import Path
        from backend.config.settings import MODELS_DIR
        from backend.models.cnn_model import DiseaseTreeCNN
        from backend.services.detection import DiseaseTreeDetectionService
        from backend.utils.image_reader import ImageReader

        # 标记任务为运行中
        task_manager.start_task(task_id)
        task_manager.update_progress(task_id, 10, "初始化检测任务")
        logger.info(f"[{task_id}] 检测任务已启动，影像数: {len(image_paths)}")

        # 第一步：加载模型配置
        task_manager.update_progress(task_id, 15, "加载模型配置")
        db_manager = get_db_manager()
        session = db_manager.get_session()

        model_task = session.query(TrainingTask).filter(
            TrainingTask.id == model_config_id,
            TrainingTask.status == "completed"
        ).first()

        session.close()

        if not model_task:
            raise ValueError(f"模型配置不存在或未完成: {model_config_id}")

        model_path = model_task.model_path
        if not model_path or not Path(model_path).exists():
            raise ValueError(f"模型文件不存在: {model_path}")

        # 解析模型配置
        try:
            model_cfg = json.loads(model_task.model_config) if model_task.model_config else {}
        except json.JSONDecodeError:
            model_cfg = {}

        logger.info(f"[{task_id}] 模型路径: {model_path}, 配置: {model_cfg}")

        # 第二步：创建模型并加载权重
        task_manager.update_progress(task_id, 20, "加载模型权重")
        device = "cuda" if torch.cuda.is_available() else "cpu"

        model = DiseaseTreeCNN(
            in_channels=model_cfg.get("in_channels", 3),
            num_timesteps=model_cfg.get("num_timesteps", 1),
            base_filters=model_cfg.get("base_filters", 32),
            num_classes=2,
        )
        model.load_state_dict(torch.load(model_path, map_location=device))
        model.to(device)
        model.eval()
        logger.info(f"[{task_id}] 模型加载成功，设备: {device}")

        # 第三步：创建检测服务
        task_manager.update_progress(task_id, 25, "初始化检测服务")
        detection_service = DiseaseTreeDetectionService(
            model=model,
            device=device,
            confidence_threshold=0.5,
        )

        # 第四步：对每个影像执行检测（强制瓦片模式）
        all_results = []
        total_images = len(image_paths)

        for img_idx, image_path in enumerate(image_paths):
            # 检查停止标志
            if task_manager.is_stop_requested(task_id):
                logger.info(f"[{task_id}] 检测任务被停止（处理第 {img_idx + 1}/{total_images} 个影像）")
                task_manager.cancel_task(task_id, "用户停止")
                return

            progress_base = 25 + int((img_idx / total_images) * 60)
            task_manager.update_progress(
                task_id, progress_base,
                f"检测影像 {img_idx + 1}/{total_images}: {Path(image_path).name}"
            )

            logger.info(f"[{task_id}] 开始检测影像: {image_path}")

            # 获取影像信息，判断是否需要瓦片模式
            success, info, msg = ImageReader.get_image_info(image_path)
            if not success:
                logger.error(f"[{task_id}] 获取影像信息失败: {image_path}, {msg}")
                continue

            W, H, B = info["width"], info["height"], info["band_count"]
            total_pixels = W * H

            # 强制对大型影像使用瓦片模式
            use_tile_mode = total_pixels > 25000000  # > 5000x5000

            if use_tile_mode:
                logger.info(
                    f"[{task_id}] 影像尺寸较大 ({W}x{H})，使用瓦片模式进行深度学习检测"
                )
                # 使用分块检测模式：先读取影像，然后分块检测
                success, image_data, msg = ImageReader.read_image(image_path)
                if not success:
                    logger.error(f"[{task_id}] 读取影像失败: {image_path}, {msg}")
                    continue

                success, result, msg = detection_service.detect_on_tiled_image(
                    image_data,
                    tile_size=1024,
                    padding_mode="pad",
                    use_parallel=True,
                    num_workers=8,
                )
            else:
                # 小影像可直接处理
                logger.info(f"[{task_id}] 影像尺寸较小 ({W}x{H})，使用直接检测模式")
                success, image_data, msg = ImageReader.read_image(image_path)
                if not success:
                    logger.error(f"[{task_id}] 读取影像失败: {image_path}, {msg}")
                    continue

                success, result, msg = detection_service.detect_on_image(image_data)

            if not success:
                logger.error(f"[{task_id}] 检测失败: {image_path}, {msg}")
                continue

            all_results.append({
                "image_path": image_path,
                "result": result,
            })

            logger.info(
                f"[{task_id}] 影像 {img_idx + 1}/{total_images} 检测完成: "
                f"检测到 {len(result.get('points', []))} 个病害木点位"
            )

        # 第五步：汇总结果
        task_manager.update_progress(task_id, 90, "处理检测结果")

        total_points = sum(len(r["result"].get("points", [])) for r in all_results)
        result_data = {
            "status": "success",
            "message": "检测任务完成",
            "image_count": len(image_paths),
            "processed_count": len(all_results),
            "model_config_id": model_config_id,
            "temporal_type": temporal_type,
            "total_detections": total_points,
            "detection_results": all_results,
        }

        logger.info(
            f"[{task_id}] 检测任务完成: "
            f"处理 {len(all_results)}/{len(image_paths)} 个影像, "
            f"共检测到 {total_points} 个病害木点位"
        )

        # 标记任务为完成
        task_manager.complete_task(task_id, result_data)

    except Exception as e:
        logger.error(f"[{task_id}] 检测任务执行失败: {str(e)}")
        import traceback
        logger.error(f"[{task_id}] 异常详情: {traceback.format_exc()}")
        task_manager.fail_task(task_id, f"检测任务执行失败: {str(e)}")
