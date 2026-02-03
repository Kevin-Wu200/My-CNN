"""
分片上传 API 接口模块

支持大文件分片上传、断点续传、并发上传等功能
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
import shutil

from backend.config.settings import (
    UPLOAD_DIR,
    DETECTION_IMAGES_DIR,
    TEMP_DIR,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])

# 上传会话存储（生产环境应使用 Redis）
upload_sessions: Dict[str, Dict[str, Any]] = {}


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
    try:
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

        # 创建上传会话目录
        session_dir = Path(TEMP_DIR) / uploadId
        session_dir.mkdir(parents=True, exist_ok=True)

        # 保存分片文件
        chunk_path = session_dir / f"chunk_{chunkIndex}"
        chunk_content = await chunk.read()

        with open(chunk_path, "wb") as f:
            f.write(chunk_content)

        logger.info(
            f"分片上传成功: uploadId={uploadId}, chunkIndex={chunkIndex}, "
            f"chunkSize={len(chunk_content)}, fileName={fileName}"
        )

        # 更新会话信息
        if uploadId not in upload_sessions:
            upload_sessions[uploadId] = {
                "fileName": fileName,
                "fileSize": fileSize,
                "totalChunks": totalChunks,
                "uploadedChunks": set(),
            }

        upload_sessions[uploadId]["uploadedChunks"].add(chunkIndex)

        return {
            "status": "success",
            "message": "分片上传成功",
            "uploadId": uploadId,
            "chunkIndex": chunkIndex,
            "uploadedChunks": len(upload_sessions[uploadId]["uploadedChunks"]),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分片上传失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"分片上传失败: {str(e)}",
        )


@router.post("/complete")
async def complete_upload(
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    完成文件上传（合并所有分片）

    Args:
        data: 包含 uploadId、fileName、fileSize、totalChunks 的字典

    Returns:
        包含最终文件路径的 JSON 响应
    """
    try:
        uploadId = data.get("uploadId")
        fileName = data.get("fileName")
        fileSize = data.get("fileSize")
        totalChunks = data.get("totalChunks")

        if not uploadId or not fileName:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="缺少必要参数: uploadId 或 fileName",
            )

        # 验证会话
        if uploadId not in upload_sessions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"上传会话不存在: {uploadId}",
            )

        session = upload_sessions[uploadId]

        # 验证所有分片是否已上传
        if len(session["uploadedChunks"]) != totalChunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"分片不完整: 已上传 {len(session['uploadedChunks'])}/{totalChunks}",
            )

        # 合并分片
        session_dir = Path(TEMP_DIR) / uploadId
        output_dir = Path(DETECTION_IMAGES_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / fileName

        with open(output_path, "wb") as output_file:
            for i in range(totalChunks):
                chunk_path = session_dir / f"chunk_{i}"
                if not chunk_path.exists():
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"分片文件丢失: chunk_{i}",
                    )

                with open(chunk_path, "rb") as chunk_file:
                    output_file.write(chunk_file.read())

        # 验证文件大小
        actual_size = output_path.stat().st_size
        if actual_size != fileSize:
            output_path.unlink()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"文件大小不匹配: 期望 {fileSize}, 实际 {actual_size}",
            )

        logger.info(
            f"文件上传完成: uploadId={uploadId}, fileName={fileName}, "
            f"fileSize={fileSize}, filePath={output_path}"
        )

        # 清理临时文件
        shutil.rmtree(session_dir, ignore_errors=True)
        del upload_sessions[uploadId]

        return {
            "status": "success",
            "message": "文件上传完成",
            "uploadId": uploadId,
            "file_path": str(output_path),
            "fileName": fileName,
            "fileSize": fileSize,
            "totalChunks": totalChunks,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件上传完成失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件上传完成失败: {str(e)}",
        )
