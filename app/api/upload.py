"""
文件上传和管理 API
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.api.auth import get_api_key
from app.core.file_storage import file_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/files", tags=["files"], dependencies=[Depends(get_api_key)])


class FileUploadResponse(BaseModel):
    """文件上传响应"""
    file_id: str = Field(..., description="文件UUID")
    filename: str = Field(..., description="原始文件名")
    file_size: int = Field(..., description="文件大小（字节）")
    message: str = Field(default="File uploaded successfully")


class FileInfo(BaseModel):
    """文件信息"""
    file_id: str = Field(..., description="文件UUID")
    filename: str = Field(..., description="原始文件名")
    file_size: int = Field(..., description="文件大小（字节）")
    content_type: str = Field(..., description="文件MIME类型")
    created_at: str = Field(..., description="上传时间")


class FileListResponse(BaseModel):
    """文件列表响应"""
    files: list[FileInfo] = Field(..., description="文件列表")
    total: int = Field(..., description="文件总数")


class FileDeleteResponse(BaseModel):
    """文件删除响应"""
    message: str = Field(..., description="删除结果")
    file_id: str = Field(..., description="删除的文件UUID")


# 支持的音频/视频格式（所有 ffmpeg 支持的格式）
SUPPORTED_FORMATS = {
    # 音频
    ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma", ".opus", ".wv", ".aiff",
    # 视频
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".mpeg", ".mpg", ".3gp", ".flv", ".wmv",
}


def _validate_file_format(filename: str) -> bool:
    """验证文件格式是否支持"""
    from pathlib import Path
    ext = Path(filename).suffix.lower()
    return ext in SUPPORTED_FORMATS


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(..., description="要上传的音视频文件"),
):
    """
    上传音视频文件
    
    支持的格式：flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav, webm 等
    
    上传成功后返回文件UUID，可用于后续转录。
    """
    # 验证文件名
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    
    # 验证文件格式
    if not _validate_file_format(file.filename):
        raise HTTPException(
            status_code=400, 
            detail=f"不支持的文件格式。支持的格式: {', '.join(sorted(SUPPORTED_FORMATS))}"
        )
    
    try:
        # 读取文件内容
        content = await file.read()
        
        # 验证文件大小（最大 2GB）
        max_size = 2 * 1024 * 1024 * 1024  # 2GB
        if len(content) > max_size:
            raise HTTPException(status_code=400, detail="文件大小超过限制（最大 2GB）")
        
        # 保存文件
        file_id = await file_storage.save_file(
            filename=file.filename,
            file_content=content,
            content_type=file.content_type or "application/octet-stream",
        )
        
        return FileUploadResponse(
            file_id=file_id,
            filename=file.filename,
            file_size=len(content),
            message="File uploaded successfully",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("文件上传失败: %s", e)
        raise HTTPException(status_code=500, detail=f"文件上传失败: {e}")


@router.get("/list", response_model=FileListResponse)
async def list_files():
    """
    列出所有已上传的文件
    
    返回文件列表，包含文件UUID、文件名、大小、上传时间等信息。
    """
    files = file_storage.list_files()
    file_list = [
        FileInfo(
            file_id=f.file_id,
            filename=f.filename,
            file_size=f.file_size,
            content_type=f.content_type,
            created_at=f.created_at,
        )
        for f in files
    ]
    return FileListResponse(files=file_list, total=len(file_list))


@router.get("/{file_id}", response_model=FileInfo)
async def get_file_info(file_id: str):
    """
    获取指定文件的信息
    
    - **file_id**: 文件UUID
    """
    metadata = file_storage.get_file(file_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    return FileInfo(
        file_id=metadata.file_id,
        filename=metadata.filename,
        file_size=metadata.file_size,
        content_type=metadata.content_type,
        created_at=metadata.created_at,
    )


@router.delete("/{file_id}", response_model=FileDeleteResponse)
async def delete_file(file_id: str):
    """
    删除指定文件
    
    - **file_id**: 文件UUID
    """
    metadata = file_storage.get_file(file_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    success = file_storage.delete_file(file_id)
    if not success:
        raise HTTPException(status_code=500, detail="文件删除失败")
    
    return FileDeleteResponse(
        message="File deleted successfully",
        file_id=file_id,
    )
