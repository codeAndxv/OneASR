"""转录记录持久化服务 — 抽离自 stream.py / audio.py。"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.db import async_session
from app.models.orm_models import FileTranscriptionRecord, StreamingRecord

logger = logging.getLogger(__name__)


# ── 文件转录记录 ─────────────────────────────────────────────────

async def save_file_transcription_record(
    *,
    record_id: str,
    filename: str,
    file_size: int = 0,
    engine_name: str,
    model_name: str | None = None,
    device_info: str | None = None,
    language: str | None = None,
    response_format: str | None = None,
    segment_count: int | None = None,
    result_length: int | None = None,
    total_time: float | None = None,
    is_completed: bool = True,
    error_message: str | None = None,
):
    """保存一条文件转录记录（成功或失败均可调用）。"""
    try:
        async with async_session() as session:
            session.add(FileTranscriptionRecord(
                record_id=record_id,
                filename=filename,
                file_size=file_size,
                engine_name=engine_name,
                model_name=model_name,
                device_info=device_info,
                language=language,
                response_format=response_format,
                segment_count=segment_count,
                result_length=result_length,
                total_time=total_time,
                is_completed=is_completed,
                error_message=error_message,
                completed_at=datetime.now(timezone.utc),
            ))
            await session.commit()
    except Exception:
        logger.warning("保存文件转录记录失败: record_id=%s", record_id)


# ── 流式识别记录 ─────────────────────────────────────────────────

async def save_streaming_record(
    *,
    record_id: str,
    engine_name: str,
    model_name: str | None = None,
    language: str | None = None,
    line_count: int = 0,
    total_time: float | None = None,
    is_completed: bool = True,
    error_message: str | None = None,
):
    """保存一条流式识别记录。"""
    try:
        async with async_session() as session:
            session.add(StreamingRecord(
                record_id=record_id,
                engine_name=engine_name,
                model_name=model_name,
                language=language,
                line_count=line_count,
                total_time=total_time,
                is_completed=is_completed,
                error_message=error_message,
                completed_at=datetime.now(timezone.utc),
            ))
            await session.commit()
    except Exception:
        logger.warning("保存流式识别记录失败: record_id=%s", record_id)
