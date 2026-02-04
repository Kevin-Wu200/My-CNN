"""
后端配置模块
用于管理系统全局配置参数
"""

import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 存储目录配置
STORAGE_DIR = PROJECT_ROOT / "storage"
UPLOAD_DIR = STORAGE_DIR / "uploads"
TRAINING_SAMPLES_DIR = STORAGE_DIR / "training_samples"
DETECTION_IMAGES_DIR = STORAGE_DIR / "detection_images"
TEMP_DIR = STORAGE_DIR / "temp"

# 模型目录配置
MODELS_DIR = STORAGE_DIR / "models"

# 日志目录配置
LOGS_DIR = PROJECT_ROOT / "logs"

# 数据库配置
DATABASE_PATH = STORAGE_DIR / "system.db"

# 影像处理配置
IMAGE_PROCESSING_CONFIG = {
    # 影像分块大小（像素）
    "chunk_width": 1024,
    "chunk_height": 1024,
    # 并行处理块数量（优化配置：8个分块并行处理）
    "parallel_chunks": 8,
    # 支持的影像格式
    "supported_formats": [".img", ".tif", ".tiff"],
}

# SLIC超像素配置
SLIC_CONFIG = {
    # 超像素数量
    "num_segments": 100,
    # 紧凑度参数
    "compactness": 10,
}

# 模型训练配置
TRAINING_CONFIG = {
    # 默认批大小
    "batch_size": 32,
    # 默认学习率
    "learning_rate": 0.001,
    # 默认epoch数
    "num_epochs": 50,
    # 训练集比例
    "train_ratio": 0.8,
    # 验证集比例
    "val_ratio": 0.2,
}

# 模型检测配置
DETECTION_CONFIG = {
    # 检测置信度阈值
    "confidence_threshold": 0.5,
    # 非极大值抑制阈值
    "nms_threshold": 0.3,
}

# 确保必要目录存在
def ensure_directories():
    """确保所有必要的目录都已创建"""
    directories = [
        UPLOAD_DIR,
        TRAINING_SAMPLES_DIR,
        DETECTION_IMAGES_DIR,
        TEMP_DIR,
        MODELS_DIR,
        LOGS_DIR,
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


# 初始化时创建目录
ensure_directories()
