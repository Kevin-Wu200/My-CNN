"""
数据库模型模块
用于定义用户、训练任务和检测任务的数据库模型
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from pathlib import Path
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 创建基类
Base = declarative_base()


class User(Base):
    """用户模型"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    phone = Column(String(11), unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    last_login = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<User(id={self.id}, phone={self.phone})>"


class TrainingTask(Base):
    """训练任务模型"""

    __tablename__ = "training_tasks"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    task_name = Column(String(200), nullable=False)
    sample_path = Column(String(500), nullable=False)
    model_config = Column(Text, nullable=False)  # JSON 格式的模型配置
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    progress = Column(Float, default=0.0)  # 0-100
    model_path = Column(String(500), nullable=True)  # 训练完成后的模型路径
    training_history = Column(Text, nullable=True)  # JSON 格式的训练历史
    error_message = Column(Text, nullable=True)  # 错误信息
    created_at = Column(DateTime, default=datetime.now)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<TrainingTask(id={self.id}, user_id={self.user_id}, status={self.status})>"


class DetectionTask(Base):
    """检测任务模型"""

    __tablename__ = "detection_tasks"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    task_name = Column(String(200), nullable=False)
    image_path = Column(String(500), nullable=False)
    model_id = Column(Integer, nullable=False)  # 使用的训练任务 ID
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    progress = Column(Float, default=0.0)  # 0-100
    detection_results = Column(Text, nullable=True)  # JSON 格式的检测结果
    change_detection_results = Column(Text, nullable=True)  # JSON 格式的变化检测结果
    error_message = Column(Text, nullable=True)  # 错误信息
    created_at = Column(DateTime, default=datetime.now)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<DetectionTask(id={self.id}, user_id={self.user_id}, status={self.status})>"


class CorrectionTask(Base):
    """标注修正任务模型"""

    __tablename__ = "correction_tasks"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    detection_task_id = Column(Integer, nullable=False)  # 关联的检测任务
    original_geojson_path = Column(String(500), nullable=False)
    corrected_geojson_path = Column(String(500), nullable=True)
    status = Column(String(50), default="pending")  # pending, corrected, reflowed
    created_at = Column(DateTime, default=datetime.now)
    corrected_at = Column(DateTime, nullable=True)
    reflowed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<CorrectionTask(id={self.id}, user_id={self.user_id}, status={self.status})>"


class UploadSession(Base):
    """文件上传会话模型"""

    __tablename__ = "upload_sessions"

    upload_id = Column(String(100), primary_key=True, index=True)
    file_name = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    total_chunks = Column(Integer, nullable=False)
    uploaded_chunks = Column(Text, nullable=False)  # JSON 序列化的已上传分片索引集合
    # 状态值: uploading(接收chunk中) -> chunks_complete(所有chunk已接收) -> merging(合并中) -> merge_complete(合并完成) -> completed(文件就绪) -> failed
    status = Column(String(50), default="uploading")
    file_path = Column(String(500), nullable=True)  # 合并完成后的文件路径
    error_message = Column(Text, nullable=True)  # 错误信息
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<UploadSession(upload_id={self.upload_id}, status={self.status}, uploaded={len(self.uploaded_chunks)}/{self.total_chunks})>"


class DatabaseManager:
    """数据库管理器"""

    def __init__(self, database_path: str):
        """
        初始化数据库管理器

        Args:
            database_path: 数据库文件路径
        """
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        # 创建数据库引擎
        self.engine = create_engine(
            f"sqlite:///{self.database_path}",
            connect_args={"check_same_thread": False},
        )

        # 创建会话工厂
        self.SessionLocal = sessionmaker(bind=self.engine)

        # 创建所有表
        Base.metadata.create_all(self.engine)

        logger.info(f"数据库初始化完成: {self.database_path}")

    def get_session(self):
        """获取数据库会话"""
        return self.SessionLocal()

    def close(self):
        """关闭数据库连接"""
        self.engine.dispose()


# 全局数据库管理器实例
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """获取全局数据库管理器实例"""
    global _db_manager
    if _db_manager is None:
        from backend.config.settings import DATABASE_PATH
        _db_manager = DatabaseManager(str(DATABASE_PATH))
    return _db_manager

