"""兼容层：已迁移至 app.schemas.audio，此处保留 re-export 以向后兼容。"""

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

__all__ = [
    "OutputFormat",
    "Segment",
    "TranscriptionRequest",
    "TranscriptionResponse",
    "FileRequest",
    "FileResponse",
    "StreamResponse",
    "StreamLine",
]
