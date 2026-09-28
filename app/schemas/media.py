"""媒体解析与下载独立任务相关的 Pydantic 数据模式。"""

from typing import Optional
from pydantic import BaseModel, Field


class ParseRequest(BaseModel):
    url: str = Field(..., description="视频 URL（抖音/TikTok/B站/YouTube）")
    format: str = Field("audio", description="下载格式：audio 或 video")


class ParseResponse(BaseModel):
    task_id: str = Field(..., description="任务 ID，用于后续查询")
    status: str = Field("pending", description="初始状态")
    platform: str = Field(..., description="检测到的平台")


class TaskInfo(BaseModel):
    task_id: str
    url: str
    platform: Optional[str] = None
    format: str
    status: str
    progress: float
    title: Optional[str] = None
    duration_seconds: Optional[float] = None
    uploader: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None


class TaskListResponse(BaseModel):
    tasks: list[TaskInfo]
    total: int


class TaskDeleteResponse(BaseModel):
    message: str
    task_id: str
