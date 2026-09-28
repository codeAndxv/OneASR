"""Pydantic 数据验证与传输模式 (Schemas)。"""

from app.schemas.audio import (
    OutputFormat,
    Segment,
    TranscriptionRequest,
    TranscriptionResponse,
    FileRequest,
    FileResponse,
    StreamResponse,
    StreamLine,
)
from app.schemas.file import (
    FileUploadResponse,
    FileInfo,
    FileListResponse,
    FileDeleteResponse,
    FetchURLRequest,
    FetchURLResponse,
    FetchURLTaskInfo,
)
from app.schemas.media import (
    ParseRequest,
    ParseResponse,
    TaskInfo as MediaTaskInfo,
    TaskListResponse as MediaTaskListResponse,
    TaskDeleteResponse as MediaTaskDeleteResponse,
)
from app.schemas.transcription import (
    TaskCreateRequest,
    TaskCreateResponse,
    TaskStatusResponse,
    TaskListResponse as TranscriptionTaskListResponse,
    TaskCancelResponse,
)

__all__ = [
    # Audio
    "OutputFormat",
    "Segment",
    "TranscriptionRequest",
    "TranscriptionResponse",
    "FileRequest",
    "FileResponse",
    "StreamResponse",
    "StreamLine",
    # File
    "FileUploadResponse",
    "FileInfo",
    "FileListResponse",
    "FileDeleteResponse",
    "FetchURLRequest",
    "FetchURLResponse",
    "FetchURLTaskInfo",
    # Media
    "ParseRequest",
    "ParseResponse",
    "MediaTaskInfo",
    "MediaTaskListResponse",
    "MediaTaskDeleteResponse",
    # Transcription
    "TaskCreateRequest",
    "TaskCreateResponse",
    "TaskStatusResponse",
    "TranscriptionTaskListResponse",
    "TaskCancelResponse",
]
