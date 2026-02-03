"""
FastAPI 主应用程序入口
用于初始化 FastAPI 应用并注册所有 API 路由
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from backend.api.training_sample import router as training_router
from backend.api.detection_config import router as detection_config_router
from backend.api.unsupervised_detection import router as unsupervised_router
from backend.api.upload import router as upload_router
from backend.api.task_status import router as task_status_router
from backend.utils.logger import LoggerSetup

# 初始化日志
logger = LoggerSetup.setup_logger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="遥感影像病害木检测系统 API",
    description="用于训练样本上传、模型训练、病害木检测的 API 接口",
    version="1.0.0",
)

# 配置 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(training_router)
app.include_router(detection_config_router)
app.include_router(unsupervised_router)
app.include_router(upload_router)
app.include_router(task_status_router)

# 健康检查端点
@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "message": "API 服务正常运行",
    }

# 根路由
@app.get("/")
async def root():
    """根路由"""
    return {
        "message": "欢迎使用遥感影像病害木检测系统 API",
        "version": "1.0.0",
        "docs": "/docs",
    }

if __name__ == "__main__":
    import uvicorn

    logger.info("启动 FastAPI 服务...")
    uvicorn.run(
        "backend.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        timeout_keep_alive=43200,  # 12小时 keep-alive 超时
        timeout_notify=43200,  # 12小时 shutdown 通知超时
    )
