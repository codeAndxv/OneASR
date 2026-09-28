"""文件上传、资产管理与网络 URL 导入相关的 Pydantic 数据模式。"""

from typing import Optional
from pydantic import BaseModel, Field


class FileUploadResponse(BaseModel):
    """文件上传响应"""
    file_id: str = Field(..., description="文件UUID")
    filename: str = Field(..., description="原始文件名")
    file_size: int = Field(..., description="文件大小（字节）")
    file_md5: str = Field(..., description="文件 MD5")
    duplicate: bool = Field(default=False, description="是否为秒传（文件已存在）")
    message: str = Field(default="File uploaded successfully")


class FileInfo(BaseModel):
    """文件信息"""
    file_id: str = Field(..., description="文件UUID")
    filename: str = Field(..., description="原始文件名")
    file_size: int = Field(..., description="文件大小（字节）")
    file_md5: str = Field(..., description="文件 MD5")
    content_type: Optional[str] = Field(None, description="文件MIME类型")
    created_at: str = Field(..., description="上传时间")


class FileListResponse(BaseModel):
    """文件列表响应"""
    files: list[FileInfo] = Field(..., description="文件列表")
    total: int = Field(..., description="文件总数")


class FileDeleteResponse(BaseModel):
    """文件删除响应"""
    message: str = Field(..., description="删除结果")
    file_id: str = Field(..., description="删除的文件UUID")


class FetchURLRequest(BaseModel):
    """从网络 URL 异步拉取并导入为文件资产"""
    url: str = Field(..., description="音视频媒体 URL (YouTube/B站/抖音等)")
    format: str = Field("audio", description="提取格式：audio 或 video")


class FetchURLResponse(BaseModel):
    """URL 拉取任务创建响应"""
    task_id: str = Field(..., description="任务 ID，用于后续轮询状态")
    status: str = Field("pending", description="初始状态")


class FetchURLTaskInfo(BaseModel):
    """URL 拉取任务状态响应"""
    task_id: str
    url: str
    status: str = Field(..., description="pending / running / succeeded / failed")
    progress: float = 0.0
    file_id: Optional[str] = Field(None, description="下载完成并注册后的文件 UUID")
    filename: Optional[str] = None
    file_size: Optional[int] = None
    title: Optional[str] = None
    duration_seconds: Optional[float] = None
    uploader: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
