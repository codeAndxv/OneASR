"""异步转录任务与流式获取相关的 Pydantic 数据模式。"""

from typing import Optional
from pydantic import BaseModel, Field


class TaskCreateRequest(BaseModel):
    file_uuid: str = Field(..., description="Uploaded file UUID")
    model: str = Field(..., description="Model identifier (engine_name/model_name)")
    language: Optional[str] = Field(None, description="Language code (ISO-639-1)")
    response_format: Optional[str] = Field("json", description="Output format")


class TaskCreateResponse(BaseModel):
    task_id: str
    status: str = "pending"
    created_at: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: float = 0.0
    filename: str
    file_size: Optional[int] = None
    source_type: str
    model: str
    language: Optional[str] = None
    response_format: Optional[str] = None
    total_time: Optional[float] = None
    segment_count: Optional[int] = None
    text: Optional[str] = None
    segments: list[dict] = Field(default_factory=list)
    error_message: Optional[str] = None
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None


class TaskListResponse(BaseModel):
    tasks: list[TaskStatusResponse]
    total: int


class TaskCancelResponse(BaseModel):
    message: str
    task_id: str
