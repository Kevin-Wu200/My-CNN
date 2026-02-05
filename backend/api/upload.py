"""
分片上传 API 接口模块

支持大文件分片上传、断点续传、并发上传等功能
"""

import logging
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from pydantic import BaseModel, field_validator
import shutil
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from collections import defaultdict
import time

from backend.config.settings import (
    UPLOAD_DIR,
    DETECTION_IMAGES_DIR,
    TEMP_DIR,
)
from backend.models.database import UploadSession, get_db_manager
from backend.utils.file_path_manager import FilePathManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])

# 获取数据库管理器
db_manager = get_db_manager()

# 步骤7: 限制 /upload/chunk 的并发或频率
# 使用简单的速率限制：每个 uploadId 在 1 秒内最多接收 10 个请求
class RateLimiter:
    """简单的速率限制器"""
    def __init__(self, max_requests: int = 10, window_seconds: int = 1):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, list] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        """检查是否允许请求"""
        now = time.time()
        # 清理过期的请求记录
        self.requests[key] = [req_time for req_time in self.requests[key]
                              if now - req_time < self.window_seconds]

        if len(self.requests[key]) >= self.max_requests:
            return False

        self.requests[key].append(now)
        return True

chunk_rate_limiter = RateLimiter(max_requests=10, window_seconds=1)


class CompleteUploadRequest(BaseModel):
    """完成上传请求模型"""
    uploadId: str
    fileName: str
    fileSize: int
    totalChunks: int

    @field_validator("fileSize", "totalChunks")
    @classmethod
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError("必须大于 0")
        return v

    @field_validator("uploadId", "fileName")
    @classmethod
    def validate_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("不能为空")
        return v


class UploadStatusResponse(BaseModel):
    """上传状态响应模型"""
    uploadId: str
    status: str  # uploading, chunks_complete, merging, merge_complete, completed, failed
    progress: int  # 0-100
    uploadedChunks: int
    totalChunks: int
    filePath: Optional[str] = None
    errorMessage: Optional[str] = None
    fileReady: bool = False  # 文件是否已就绪（仅当 status=completed 时为 True）


@router.post("/chunk")
async def upload_chunk(
    chunk: UploadFile = File(...),
    chunkIndex: int = Form(...),
    totalChunks: int = Form(...),
    fileName: str = Form(...),
    fileSize: int = Form(...),
    uploadId: str = Form(...),
) -> Dict[str, Any]:
    """
    上传单个文件分片

    Args:
        chunk: 分片数据
        chunkIndex: 分片索引（0-based）
        totalChunks: 总分片数
        fileName: 原始文件名
        fileSize: 原始文件大小
        uploadId: 上传会话 ID

    Returns:
        包含上传结果的 JSON 响应
    """
    db_session = db_manager.get_session()
    try:
        # 步骤7: 限制并发或频率
        if not chunk_rate_limiter.is_allowed(uploadId):
            logger.warning(
                f"[RATE_LIMIT_EXCEEDED] uploadId={uploadId}, chunkIndex={chunkIndex}"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="请求过于频繁，请稍后重试",
            )

        # 验证参数
        if chunkIndex < 0 or chunkIndex >= totalChunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的分片索引: {chunkIndex}",
            )

        if not fileName:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件名不能为空",
            )

        # 步骤7: 统一文件路径来源 - 使用 FilePathManager 获取路径
        session_dir = FilePathManager.get_chunk_dir(uploadId)
        FilePathManager.ensure_directory_exists(session_dir)

        # 保存分片文件
        chunk_path = FilePathManager.get_chunk_path(uploadId, chunkIndex)
        chunk_content = await chunk.read()

        with open(chunk_path, "wb") as f:
            f.write(chunk_content)

        # 步骤8: 明确区分三类信息 - chunk 接收日志
        logger.info(
            f"[CHUNK_RECEIVED] uploadId={uploadId}, chunkIndex={chunkIndex}, "
            f"chunkSize={len(chunk_content)}, fileName={fileName}"
        )

        # 从数据库获取或创建会话
        upload_session = db_session.query(UploadSession).filter(
            UploadSession.upload_id == uploadId
        ).first()

        if not upload_session:
            # 创建新会话
            uploaded_chunks_set = {chunkIndex}
            upload_session = UploadSession(
                upload_id=uploadId,
                file_name=fileName,
                file_size=fileSize,
                total_chunks=totalChunks,
                uploaded_chunks=json.dumps(list(uploaded_chunks_set)),
                status="uploading",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db_session.add(upload_session)
            logger.info(
                f"[SESSION_CREATED] uploadId={uploadId}, totalChunks={totalChunks}, "
                f"fileName={fileName}, fileSize={fileSize}"
            )
        else:
            # 更新现有会话
            uploaded_chunks_set = set(json.loads(upload_session.uploaded_chunks))
            uploaded_chunks_set.add(chunkIndex)
            upload_session.uploaded_chunks = json.dumps(list(uploaded_chunks_set))
            upload_session.updated_at = datetime.now()

        db_session.commit()

        uploaded_count = len(json.loads(upload_session.uploaded_chunks))
        progress = int((uploaded_count / totalChunks) * 100)

        # 步骤8: 明确区分三类信息 - chunk 接收日志
        logger.info(
            f"[CHUNKS_UPDATED] uploadId={uploadId}, uploaded={uploaded_count}/{totalChunks}, "
            f"progress={progress}%"
        )

        return {
            "status": "success",
            "message": "分片上传成功",
            "uploadId": uploadId,
            "chunkIndex": chunkIndex,
            "uploadedChunks": uploaded_count,
            "totalChunks": totalChunks,
            "progress": progress,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CHUNK_UPLOAD_ERROR] uploadId={uploadId}, chunkIndex={chunkIndex}, error={str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"分片上传失败: {str(e)}",
        )
    finally:
        db_session.close()


@router.post("/complete")
async def complete_upload(
    request: CompleteUploadRequest,
) -> Dict[str, Any]:
    """
    完成文件上传（提交合并任务）

    Args:
        request: 包含 uploadId、fileName、fileSize、totalChunks 的请求体

    Returns:
        包含任务 ID 的 JSON 响应（202 Accepted）
    """
    db_session = db_manager.get_session()
    try:
        uploadId = request.uploadId
        fileName = request.fileName
        fileSize = request.fileSize
        totalChunks = request.totalChunks

        logger.info(
            f"[COMPLETE_REQUEST] uploadId={uploadId}, fileName={fileName}, "
            f"fileSize={fileSize}, totalChunks={totalChunks}"
        )

        if not uploadId or not fileName:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="缺少必要参数: uploadId 或 fileName",
            )

        if fileSize <= 0 or totalChunks <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="fileSize 和 totalChunks 必须大于 0",
            )

        # 从数据库查询会话
        upload_session = db_session.query(UploadSession).filter(
            UploadSession.upload_id == uploadId
        ).first()

        if not upload_session:
            logger.error(f"[SESSION_NOT_FOUND] uploadId={uploadId}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"上传会话不存在: {uploadId}",
            )

        # 步骤3: 当且仅当所有 chunk 接收完成后，才触发合并逻辑
        # 验证所有分片是否已上传
        uploaded_chunks_set = set(json.loads(upload_session.uploaded_chunks))
        uploaded_count = len(uploaded_chunks_set)

        if uploaded_count != totalChunks:
            missing_chunks = set(range(totalChunks)) - uploaded_chunks_set
            logger.warning(
                f"[CHUNKS_INCOMPLETE] uploadId={uploadId}, uploaded={uploaded_count}/{totalChunks}, "
                f"missing={sorted(missing_chunks)}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"分片不完整: 已上传 {uploaded_count}/{totalChunks}，缺失分片: {sorted(missing_chunks)}",
            )

        # 验证分片索引是否连续（0 到 totalChunks-1）
        expected_chunks = set(range(totalChunks))
        if uploaded_chunks_set != expected_chunks:
            logger.error(
                f"[CHUNKS_INVALID] uploadId={uploadId}, expected={expected_chunks}, "
                f"actual={uploaded_chunks_set}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"分片索引不连续",
            )

        # 步骤8: 明确区分三类信息 - chunk 接收完整日志
        logger.info(f"[ALL_CHUNKS_RECEIVED] uploadId={uploadId}, totalChunks={totalChunks}")

        # 步骤2: 在后端维护每个文件的上传状态 - 更新为 chunks_complete
        upload_session.status = "chunks_complete"
        upload_session.updated_at = datetime.now()
        db_session.commit()

        logger.info(f"[CHUNKS_COMPLETE_STATUS_SET] uploadId={uploadId}")

        # 步骤2: 在后端维护每个文件的上传状态 - 更新为 merging
        upload_session.status = "merging"
        upload_session.updated_at = datetime.now()
        db_session.commit()

        # 步骤8: 明确区分三类信息 - 文件合并日志
        logger.info(f"[MERGE_START] uploadId={uploadId}, fileName={fileName}, fileSize={fileSize}")

        # 提交后台合并任务
        from backend.services.background_task_manager import get_task_manager
        task_manager = get_task_manager()

        task_id = task_manager.submit_merge_task(
            uploadId=uploadId,
            fileName=fileName,
            fileSize=fileSize,
            totalChunks=totalChunks,
        )

        logger.info(f"[MERGE_TASK_SUBMITTED] uploadId={uploadId}, taskId={task_id}")

        return {
            "status": "accepted",
            "message": "文件合并任务已提交",
            "uploadId": uploadId,
            "taskId": task_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[COMPLETE_ERROR] uploadId={request.uploadId}, error={str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"完成上传失败: {str(e)}",
        )
    finally:
        db_session.close()


@router.get("/status/{uploadId}")
async def get_upload_status(uploadId: str) -> UploadStatusResponse:
    """
    查询上传状态

    Args:
        uploadId: 上传会话 ID

    Returns:
        上传状态信息
    """
    db_session = db_manager.get_session()
    try:
        upload_session = db_session.query(UploadSession).filter(
            UploadSession.upload_id == uploadId
        ).first()

        if not upload_session:
            logger.warning(f"[STATUS_NOT_FOUND] uploadId={uploadId}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"上传会话不存在: {uploadId}",
            )

        uploaded_chunks_set = set(json.loads(upload_session.uploaded_chunks))
        uploaded_count = len(uploaded_chunks_set)
        progress = int((uploaded_count / upload_session.total_chunks) * 100)

        # 步骤8: 明确区分三类信息 - 状态查询日志
        logger.info(
            f"[STATUS_QUERY] uploadId={uploadId}, status={upload_session.status}, "
            f"progress={progress}%, uploadedChunks={uploaded_count}/{upload_session.total_chunks}"
        )

        # 文件就绪的条件：状态为 completed
        file_ready = upload_session.status == "completed"

        return UploadStatusResponse(
            uploadId=uploadId,
            status=upload_session.status,
            progress=progress,
            uploadedChunks=uploaded_count,
            totalChunks=upload_session.total_chunks,
            filePath=upload_session.file_path,
            errorMessage=upload_session.error_message,
            fileReady=file_ready,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[STATUS_ERROR] uploadId={uploadId}, error={str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询上传状态失败: {str(e)}",
        )
    finally:
        db_session.close()


@router.delete("/cleanup")
async def cleanup_old_sessions() -> Dict[str, Any]:
    """
    清理超过 24 小时未完成的上传会话

    Returns:
        清理结果统计
    """
    db_session = db_manager.get_session()
    try:
        # 计算 24 小时前的时间
        cutoff_time = datetime.now() - timedelta(hours=24)

        # 查询超时的会话
        old_sessions = db_session.query(UploadSession).filter(
            UploadSession.status.in_(["uploading", "merging"]),
            UploadSession.updated_at < cutoff_time,
        ).all()

        cleaned_count = 0
        for session in old_sessions:
            try:
                # 步骤7: 统一文件路径来源 - 使用 FilePathManager 获取临时目录
                session_dir = FilePathManager.get_chunk_dir(session.upload_id)
                if session_dir.exists():
                    shutil.rmtree(session_dir, ignore_errors=True)
                    logger.info(f"[CLEANUP_TEMP] uploadId={session.upload_id}")

                # 标记为失败
                session.status = "failed"
                session.error_message = "上传超时，会话已清理"
                session.updated_at = datetime.now()
                cleaned_count += 1

                logger.info(f"[SESSION_CLEANED] uploadId={session.upload_id}")
            except Exception as e:
                logger.error(f"[CLEANUP_ERROR] uploadId={session.upload_id}, error={str(e)}")

        db_session.commit()

        logger.info(f"[CLEANUP_COMPLETE] cleaned={cleaned_count} sessions")

        return {
            "status": "success",
            "message": f"清理了 {cleaned_count} 个超时会话",
            "cleaned_count": cleaned_count,
        }

    except Exception as e:
        logger.error(f"[CLEANUP_FAILED] error={str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清理会话失败: {str(e)}",
        )
    finally:
        db_session.close()
