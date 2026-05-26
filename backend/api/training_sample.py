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
                detail={
                    "error": "不支持的文件格式",
                    "message": f"不支持的文件格式: {file_ext}，仅支持 .zip 和 .rar 压缩包格式",
                    "expected_formats": [".zip", ".rar"],
                    "received_format": file_ext,
                    "guidance": "训练样本必须以 ZIP 或 RAR 压缩包形式上传。"
                                "压缩包内部必须包含：\n"
                                "1. 训练影像文件（支持 jpg / png / tif / tiff 格式），按时间顺序用数字命名（如 1.jpg, 2.jpg...）\n"
                                "2. 一个 GeoJSON 标注文件（.geojson），包含病害木点位矢量信息",
                },
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
                detail={
                    "error": "解压失败",
                    "message": message,
                    "guidance": "请确保：\n"
                                "1. 压缩包未损坏\n"
                                "2. 压缩包格式正确（ZIP 或 RAR）\n"
                                "3. 压缩包内部包含影像文件和 GeoJSON 标注文件",
                },
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
                detail={
                    "error": "训练样本验证失败",
                    "message": validation_message,
                    "guidance": "训练样本压缩包必须满足以下要求：\n"
                                "1. 包含至少一个影像文件（支持 jpg / png / tif / tiff 格式）\n"
                                "2. 包含一个 .geojson 格式的标注文件\n"
                                "3. 影像文件名按时间顺序用数字命名（如 1.jpg, 2.jpg, 3.jpg...）\n"
                                "4. 坐标系统需保持一致",
                },
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

    接入真实的 TrainingService 训练流程：
    1. 加载训练样本（影像 + GeoJSON 标注）
    2. 构建正负样本
    3. 划分训练集/验证集
    4. 创建 CNN 模型并训练
    5. 保存模型和训练历史

    Args:
        task_id: 任务ID
        sample_path: 训练样本路径
        task_name: 训练任务名称
    """
    try:
        from backend.config.settings import TRAINING_CONFIG, MODELS_DIR
        from backend.services.sample_construction import SampleConstructionService
        from backend.utils.image_reader import ImageReader
        from backend.models.cnn_model import DiseaseTreeCNN
        from backend.models.training_dataset import create_dataloaders
        from backend.services.training import TrainingService
        from backend.utils.file_path_manager import FilePathManager
        import json

        # 标记任务为运行中
        task_manager.start_task(task_id)
        task_manager.update_progress(task_id, 5, "初始化训练任务")
        logger.info(f"[{task_id}] 训练任务已启动，样本路径: {sample_path}")

        sample_dir = Path(sample_path)

        # 第一步：查找样本文件
        task_manager.update_progress(task_id, 10, "扫描训练样本文件")
        image_files = sorted([
            str(p) for p in sample_dir.rglob("*")
            if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".tif", ".tiff", ".img"]
        ])
        geojson_files = list(sample_dir.rglob("*.geojson"))

        if not image_files:
            raise ValueError(f"未找到影像文件，请确保样本目录中包含 jpg/png/tif 格式的影像")

        if not geojson_files:
            raise ValueError(f"未找到 GeoJSON 标注文件，请确保样本目录中包含 .geojson 文件")

        # 第二步：收集影像文件路径（不加载完整影像到内存，避免 4GB+ TIFF 导致 OOM）
        task_manager.update_progress(task_id, 20, "扫描训练影像文件")
        logger.info(
            f"[{task_id}] 发现 {len(image_files)} 个影像文件, GeoJSON: {geojson_path}"
        )

        # 第三步：读取 GeoJSON 并构建样本（使用流式方式，按需从磁盘读取）
        task_manager.update_progress(task_id, 30, "构建训练样本（流式模式）")
        success, points, msg = SampleConstructionService.read_geojson_points(geojson_path)
        if not success:
            raise ValueError(f"读取 GeoJSON 标注失败: {msg}")

        logger.info(f"[{task_id}] 读取到 {len(points)} 个病害木点位")

        # 裁剪正样本 patches（流式：按需从磁盘读取每个 Patch 区域）
        patch_size = 64
        success, positive_patches, msg = SampleConstructionService.crop_patches_from_files(
            image_files, points, patch_size=patch_size
        )
        if not success:
            raise ValueError(f"裁剪正样本失败: {msg}")

        num_positive = len(positive_patches)
        logger.info(f"[{task_id}] 正样本数量: {num_positive}")

        # 生成负样本（流式：按需从磁盘读取随机点位的 Patch 区域）
        num_negative = min(num_positive * 2, 500)
        success, negative_patches, msg = SampleConstructionService.generate_negative_samples_from_files(
            image_files, points,
            num_negative_samples=num_negative,
            patch_size=patch_size,
            min_distance=100,
        )
        if not success:
            logger.warning(f"[{task_id}] 负样本生成失败: {msg}，仅使用正样本")
            negative_patches = []

        logger.info(f"[{task_id}] 负样本数量: {len(negative_patches)}")

        # 合并样本并生成标签
        all_samples = positive_patches + negative_patches
        all_labels = np.concatenate([
            np.ones(len(positive_patches), dtype=np.int32),
            np.zeros(len(negative_patches), dtype=np.int32),
        ])

        if len(all_samples) < 10:
            raise ValueError(f"样本数量不足 ({len(all_samples)})，至少需要10个样本")

        # 第四步：划分训练集/验证集
        task_manager.update_progress(task_id, 45, "划分训练集和验证集")
        success, split_result, msg = SampleConstructionService.split_train_val_test(
            all_samples, all_labels,
            train_ratio=TRAINING_CONFIG["train_ratio"],
            val_ratio=TRAINING_CONFIG["val_ratio"],
            test_ratio=0.0,
        )
        if not success:
            # 回退：简单划分
            from sklearn.model_selection import train_test_split
            train_indices, val_indices = train_test_split(
                np.arange(len(all_samples)),
                train_size=TRAINING_CONFIG["train_ratio"],
                random_state=42,
                stratify=all_labels,
            )
            train_samples = [all_samples[i] for i in train_indices]
            train_labels = all_labels[train_indices]
            val_samples = [all_samples[i] for i in val_indices]
            val_labels = all_labels[val_indices]
        else:
            train_samples = split_result["train"]["samples"]
            train_labels = split_result["train"]["labels"]
            val_samples = split_result["val"]["samples"]
            val_labels = split_result["val"]["labels"]

        logger.info(
            f"[{task_id}] 样本划分: train={len(train_samples)}, val={len(val_samples)}"
        )

        # 第五步：创建 DataLoader
        task_manager.update_progress(task_id, 50, "创建数据加载器")
        batch_size = TRAINING_CONFIG["batch_size"]
        train_loader, val_loader = create_dataloaders(
            train_samples, train_labels,
            val_samples, val_labels,
            batch_size=batch_size,
            num_workers=2,
        )

        # 第六步：创建模型
        task_manager.update_progress(task_id, 55, "创建 CNN 模型")
        # 确定输入通道数和时相数
        sample_shape = all_samples[0].shape  # (T, H, W, C)
        num_timesteps = sample_shape[0]
        in_channels = sample_shape[3]

        model = DiseaseTreeCNN(
            in_channels=in_channels,
            num_timesteps=num_timesteps,
            base_filters=32,
            num_classes=2,
            dropout_rate=0.5,
        )

        # 检测并使用 GPU
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"[{task_id}] 使用设备: {device}")

        # 第七步：训练模型
        task_manager.update_progress(task_id, 60, "开始模型训练")
        model_save_dir = FilePathManager.get_models_dir() / task_id
        model_save_dir.mkdir(parents=True, exist_ok=True)

        training_service = TrainingService(
            model=model,
            device=device,
            model_save_dir=model_save_dir,
        )

        num_epochs = TRAINING_CONFIG["num_epochs"]
        learning_rate = TRAINING_CONFIG["learning_rate"]

        # 训练（带进度回调）
        history = training_service.train(
            train_loader=train_loader,
            val_loader=val_loader,
            num_epochs=num_epochs,
            learning_rate=learning_rate,
            save_best_model=True,
        )

        # 第八步：保存最终模型
        task_manager.update_progress(task_id, 95, "保存模型和训练历史")
        model_path = model_save_dir / "final_model.pth"
        torch.save(model.state_dict(), model_path)

        history_path = model_save_dir / "training_history.json"
        training_service.save_training_history(str(history_path))

        training_summary = training_service.get_training_summary()

        logger.info(
            f"[{task_id}] 训练完成: "
            f"best_val_loss={training_summary.get('best_val_loss', 'N/A'):.4f}, "
            f"best_val_accuracy={training_summary.get('best_val_accuracy', 'N/A'):.4f}, "
            f"best_val_f1={training_summary.get('best_val_f1', 'N/A'):.4f}"
        )

        # 返回训练结果
        result_data = {
            "status": "success",
            "message": "训练任务完成",
            "task_name": task_name,
            "sample_path": sample_path,
            "model_path": str(model_path),
            "history_path": str(history_path),
            "training_summary": training_summary,
            "num_samples": len(all_samples),
            "num_positive": int(num_positive),
            "num_negative": len(negative_patches),
            "num_epochs": num_epochs,
            "device": device,
        }

        logger.info(f"[{task_id}] 训练任务完成")

        # 标记任务为完成
        task_manager.complete_task(task_id, result_data)

    except Exception as e:
        logger.error(f"[{task_id}] 训练任务执行失败: {str(e)}")
        import traceback
        logger.error(f"[{task_id}] 异常详情: {traceback.format_exc()}")
        task_manager.fail_task(task_id, f"训练任务执行失败: {str(e)}")
