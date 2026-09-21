"""Async transcription tasks API — upload → create → stream.

Supports files up to 2 GB and long-running transcriptions (hours).

Endpoints:
  POST   /v1/file/transcriptions                  Create a transcription task
  GET    /v1/file/transcriptions                   List tasks (with filters)
  GET    /v1/file/transcriptions/{task_id}         Get task status + all segments
  GET    /v1/file/transcriptions/{task_id}/stream  SSE streaming result
  DELETE /v1/file/transcriptions/{task_id}         Cancel a task
"""

import asyncio
import json
import logging
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func

from app.api.auth import get_api_key
from app.core.config import app_config
from app.db import async_session
from app.engines.registry import get_engine
from app.models.orm_models import TranscriptionTask, TranscriptionSegment
from app.services.file_service import get_uploaded_file
from app.utils.audio import convert_to_wav

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/file", tags=["file"], dependencies=[Depends(get_api_key)])

MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB
MAX_URL_DOWNLOAD_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB
NATIVE_AUDIO_FORMATS = {".wav"}


# ── Pydantic response models ─────────────────────────────────────

class TaskCreateRequest(BaseModel):
    file_uuid: Optional[str] = Field(None, description="Uploaded file UUID")
    file_url: Optional[str] = Field(None, description="Audio file URL")
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


# ── Helpers ──────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _task_to_status(t: TranscriptionTask, segments: list[dict] | None = None) -> TaskStatusResponse:
    return TaskStatusResponse(
        task_id=t.task_id,
        status=t.status,
        progress=t.progress,
        filename=t.filename,
        file_size=t.file_size,
        source_type=t.source_type,
        model=t.model,
        language=t.language,
        response_format=t.response_format,
        total_time=t.total_time,
        segment_count=t.segment_count,
        text=t.result_text,
        segments=segments or [],
        error_message=t.error_message,
        created_at=t.created_at.isoformat() if t.created_at else "",
        updated_at=t.updated_at.isoformat() if t.updated_at else "",
        completed_at=t.completed_at.isoformat() if t.completed_at else None,
    )


def _ensure_wav(data: bytes, filename: str, rid: str) -> bytes:
    ext = Path(filename).suffix.lower()
    if ext in NATIVE_AUDIO_FORMATS:
        return data
    logger.info("[tasks][%s] 格式 %s 需要转换为 WAV", rid, ext)
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_in:
        tmp_in.write(data)
        tmp_in_path = Path(tmp_in.name)
    tmp_wav: Path | None = None
    try:
        tmp_wav = convert_to_wav(tmp_in_path)
        return tmp_wav.read_bytes()
    finally:
        tmp_in_path.unlink(missing_ok=True)
        if tmp_wav:
            tmp_wav.unlink(missing_ok=True)


# ── Background worker ────────────────────────────────────────────

async def _run_transcription(task_id: str):
    """Background coroutine: load audio → stream transcribe → persist segments incrementally."""
    async with async_session() as session:
        result = await session.execute(
            select(TranscriptionTask).where(TranscriptionTask.task_id == task_id)
        )
        task = result.scalar_one_or_none()
        if task is None:
            logger.error("[tasks][%s] 任务不存在", task_id)
            return

        task.status = "processing"
        task.progress = 0.0
        task.updated_at = datetime.now(timezone.utc)
        await session.commit()

    t_start = time.time()
    rid = task_id[:8]

    try:
        # 1. Load audio data based on source_type
        data: bytes = b""
        filename = task.filename

        if task.source_type == "file_url":
            logger.info("[tasks][%s] 从 URL 下载: %s", rid, task.file_url)
            async with httpx.AsyncClient(timeout=600.0) as client:
                response = await client.get(task.file_url)
                response.raise_for_status()
                data = response.content
            filename = Path(task.file_url.split("?")[0]).name or "audio.wav"
            task.file_size = len(data)

        elif task.source_type == "file_uuid":
            info = await get_uploaded_file(task.file_uuid)
            if info is None:
                raise FileNotFoundError(f"File not found: {task.file_uuid}")
            data = info.read_bytes()
            filename = info.filename
            task.file_size = len(data)

        else:  # file — stored in temp during create; reload from uploads dir
            import glob as _glob
            pattern = f"./uploads/{task.file_uuid}.*"
            matches = _glob.glob(pattern)
            if not matches:
                raise FileNotFoundError(f"File not found: {task.file_uuid}")
            storage_path = Path(matches[0])
            data = storage_path.read_bytes()
            task.file_size = len(data)

        size_mb = len(data) / (1024 * 1024)
        if len(data) > MAX_FILE_SIZE:
            raise ValueError(f"File size {size_mb:.1f}MB exceeds limit (maximum 2GB)")

        logger.info("[tasks][%s] 音频就绪: %s, %.2f MB", rid, filename, size_mb)

        # 2. Ensure WAV
        data = _ensure_wav(data, filename, rid)
        logger.info("[tasks][%s] WAV 转换完成", rid)

        # 3. Get engine
        eng = get_engine(task.model)
        logger.info("[tasks][%s] 引擎就绪: %s", rid, task.model)

        async with async_session() as session:
            result = await session.execute(
                select(TranscriptionTask).where(TranscriptionTask.task_id == task_id)
            )
            t = result.scalar_one_or_none()
            if t:
                t.progress = 0.1
                t.updated_at = datetime.now(timezone.utc)
                await session.commit()

        # 4. Stream transcribe — save each segment to DB immediately
        t_recog = time.time()
        full_text = ""
        segment_index = 0

        async for seg in eng.transcribe_file_stream(data):
            full_text += seg.text

            async with async_session() as session:
                segment = TranscriptionSegment(
                    task_id=task_id,
                    segment_index=segment_index,
                    start=seg.start,
                    end=seg.end,
                    text=seg.text,
                )
                session.add(segment)
                await session.commit()

            segment_index += 1

            # Update progress
            if seg.end > 0:
                async with async_session() as session:
                    result = await session.execute(
                        select(TranscriptionTask).where(TranscriptionTask.task_id == task_id)
                    )
                    t = result.scalar_one_or_none()
                    if t and t.status == "processing":
                        t.progress = min(0.9, 0.1 + (seg.end / 3600) * 0.8)
                        t.updated_at = datetime.now(timezone.utc)
                        await session.commit()

        recog_time = time.time() - t_recog
        total_time = time.time() - t_start

        # Get duration from last segment
        async with async_session() as session:
            result = await session.execute(
                select(TranscriptionSegment)
                .where(TranscriptionSegment.task_id == task_id)
                .order_by(TranscriptionSegment.segment_index.desc())
                .limit(1)
            )
            last_seg = result.scalar_one_or_none()
            duration = last_seg.end if last_seg else 0.0

        logger.info("[tasks][%s] 转录完成: %d 段, %d 字符, %.2fs",
                     rid, segment_index, len(full_text), recog_time)

        # 5. Persist final result
        async with async_session() as session:
            result = await session.execute(
                select(TranscriptionTask).where(TranscriptionTask.task_id == task_id)
            )
            t = result.scalar_one_or_none()
            if t:
                t.status = "completed"
                t.progress = 1.0
                t.result_text = full_text
                t.result_duration = duration
                t.segment_count = segment_index
                t.total_time = total_time
                t.device_info = eng.device if hasattr(eng, "device") else None
                t.completed_at = datetime.now(timezone.utc)
                t.updated_at = datetime.now(timezone.utc)
                await session.commit()

        logger.info("[tasks][%s] 结果已持久化", rid)

    except asyncio.CancelledError:
        async with async_session() as session:
            result = await session.execute(
                select(TranscriptionTask).where(TranscriptionTask.task_id == task_id)
            )
            t = result.scalar_one_or_none()
            if t:
                t.status = "cancelled"
                t.error_message = "Task cancelled by user"
                t.updated_at = datetime.now(timezone.utc)
                await session.commit()
        logger.info("[tasks][%s] 任务已取消", rid)

    except Exception as e:
        logger.exception("[tasks][%s] 转录失败: %s", rid, e)
        async with async_session() as session:
            result = await session.execute(
                select(TranscriptionTask).where(TranscriptionTask.task_id == task_id)
            )
            t = result.scalar_one_or_none()
            if t:
                t.status = "failed"
                t.error_message = str(e)
                t.total_time = time.time() - t_start
                t.updated_at = datetime.now(timezone.utc)
                await session.commit()


# In-memory store of running tasks for cancellation
_running_tasks: dict[str, asyncio.Task] = {}


# ── Create task ──────────────────────────────────────────────────

@router.post("/transcriptions", response_model=TaskCreateResponse)
async def create_transcription_task(
    req: TaskCreateRequest,
):
    """创建异步转录任务。

    通过 file_url 或 file_uuid 创建后台异步转录任务（application/json）。
    适用于大文件和长时间转录。
    """
    task_id = str(uuid.uuid4())
    rid = task_id[:8]
    now = datetime.now(timezone.utc)

    # Determine source and filename
    source_type = ""
    filename = "unknown"
    file_size: int | None = None
    saved_file_uuid: str | None = None

    if req.file_url:
        source_type = "file_url"
        filename = Path(req.file_url.split("?")[0]).name or "audio.wav"
        logger.info("[tasks][%s] URL source: %s", rid, req.file_url)

    elif req.file_uuid:
        source_type = "file_uuid"
        info = await get_uploaded_file(req.file_uuid)
        if info is None:
            raise HTTPException(status_code=404, detail=f"File not found: {req.file_uuid}")
        filename = info.filename
        file_size = info.file_size if hasattr(info, "file_size") else None
        saved_file_uuid = req.file_uuid
        logger.info("[tasks][%s] UUID source: %s (%s)", rid, req.file_uuid, filename)

    else:
        raise HTTPException(status_code=400, detail="Must provide either file_uuid or file_url parameter")

    # Create DB record
    async with async_session() as session:
        task = TranscriptionTask(
            task_id=task_id,
            status="pending",
            progress=0.0,
            source_type=source_type,
            filename=filename,
            file_size=file_size,
            file_url=req.file_url if source_type == "file_url" else None,
            file_uuid=saved_file_uuid,
            model=req.model,
            language=req.language,
            response_format=req.response_format or "json",
            created_at=now,
            updated_at=now,
        )
        session.add(task)
        await session.commit()

    # Schedule background work
    async_task = asyncio.create_task(_run_transcription(task_id))
    _running_tasks[task_id] = async_task

    # Auto-cleanup reference when done
    async def _cleanup(_tid: str = task_id):
        await async_task
        _running_tasks.pop(_tid, None)
    asyncio.create_task(_cleanup())

    logger.info("[tasks][%s] 任务已创建: model=%s lang=%s file=%s", rid, req.model, req.language, filename)

    return TaskCreateResponse(
        task_id=task_id,
        status="pending",
        created_at=now.isoformat(),
    )


# ── Get task status ──────────────────────────────────────────────

@router.get("/transcriptions/{task_id}", response_model=TaskStatusResponse)
async def get_transcription_task(task_id: str):
    """查询转录任务状态，包含所有已识别的分段结果。"""
    async with async_session() as session:
        result = await session.execute(
            select(TranscriptionTask).where(TranscriptionTask.task_id == task_id)
        )
        task = result.scalar_one_or_none()

    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    # Load segments
    async with async_session() as session:
        result = await session.execute(
            select(TranscriptionSegment)
            .where(TranscriptionSegment.task_id == task_id)
            .order_by(TranscriptionSegment.segment_index)
        )
        db_segments = result.scalars().all()
        segments = [
            {"id": s.segment_index, "start": s.start, "end": s.end, "text": s.text}
            for s in db_segments
        ]

    return _task_to_status(task, segments)


# ── Stream task result (SSE) ──────────────────────────────────────

@router.get("/transcriptions/{task_id}/stream")
async def stream_transcription_result(task_id: str):
    """SSE 流式获取转录结果，通过轮询数据库新行实现。"""
    async with async_session() as session:
        result = await session.execute(
            select(TranscriptionTask).where(TranscriptionTask.task_id == task_id)
        )
        task = result.scalar_one_or_none()

    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    if task.status == "completed":
        # Already completed: push all segments at once
        async with async_session() as session:
            result = await session.execute(
                select(TranscriptionSegment)
                .where(TranscriptionSegment.task_id == task_id)
                .order_by(TranscriptionSegment.segment_index)
            )
            db_segments = result.scalars().all()

        async def _emit_completed():
            for seg in db_segments:
                event = {
                    "type": "transcript.text.delta",
                    "delta": seg.text,
                    "start": seg.start,
                    "end": seg.end,
                    "is_endpoint": True,
                }
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            done_event = {"type": "transcript.text.done", "text": task.result_text or ""}
            yield f"data: {json.dumps(done_event, ensure_ascii=False)}\n\n"

        return StreamingResponse(_emit_completed(), media_type="text/event-stream")

    if task.status == "failed":
        raise HTTPException(status_code=500, detail=f"Task failed: {task.error_message}")

    if task.status == "cancelled":
        raise HTTPException(status_code=410, detail="Task was cancelled")

    # For pending/processing tasks: poll DB for new segments
    last_segment_index = -1

    async def _generate():
        nonlocal last_segment_index
        heartbeat_interval = 30
        last_heartbeat = time.time()

        while True:
            # Query new segments
            async with async_session() as session:
                result = await session.execute(
                    select(TranscriptionSegment)
                    .where(TranscriptionSegment.task_id == task_id)
                    .where(TranscriptionSegment.segment_index > last_segment_index)
                    .order_by(TranscriptionSegment.segment_index)
                )
                new_segments = result.scalars().all()

            for seg in new_segments:
                event = {
                    "type": "transcript.text.delta",
                    "delta": seg.text,
                    "start": seg.start,
                    "end": seg.end,
                    "is_endpoint": True,
                }
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                last_segment_index = seg.segment_index

            # Check task status
            async with async_session() as session:
                result = await session.execute(
                    select(TranscriptionTask).where(TranscriptionTask.task_id == task_id)
                )
                current_task = result.scalar_one_or_none()

            if current_task.status == "completed":
                done_event = {"type": "transcript.text.done", "text": current_task.result_text or ""}
                yield f"data: {json.dumps(done_event, ensure_ascii=False)}\n\n"
                break
            elif current_task.status == "failed":
                error_event = {"type": "task.failed", "error": current_task.error_message}
                yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
                break
            elif current_task.status == "cancelled":
                error_event = {"type": "task.failed", "error": "Task cancelled"}
                yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
                break

            # Heartbeat
            if time.time() - last_heartbeat > heartbeat_interval:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                last_heartbeat = time.time()

            # Poll interval
            await asyncio.sleep(0.1)  # 100ms

    return StreamingResponse(_generate(), media_type="text/event-stream")


# ── Cancel task ──────────────────────────────────────────────────

@router.delete("/transcriptions/{task_id}", response_model=TaskCancelResponse)
async def cancel_transcription_task(task_id: str):
    """取消转录任务（仅 pending / processing 状态可取消）。"""
    async with async_session() as session:
        result = await session.execute(
            select(TranscriptionTask).where(TranscriptionTask.task_id == task_id)
        )
        task = result.scalar_one_or_none()

    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    if task.status not in ("pending", "processing"):
        raise HTTPException(status_code=400, detail=f"Task status is {task.status}, cannot cancel")

    # Cancel asyncio task
    async_task = _running_tasks.pop(task_id, None)
    if async_task and not async_task.done():
        async_task.cancel()

    # Update DB
    async with async_session() as session:
        result = await session.execute(
            select(TranscriptionTask).where(TranscriptionTask.task_id == task_id)
        )
        t = result.scalar_one_or_none()
        if t:
            t.status = "cancelled"
            t.error_message = "Cancelled by user"
            t.updated_at = datetime.now(timezone.utc)
            await session.commit()

    return TaskCancelResponse(message="Task cancelled", task_id=task_id)


# ── List tasks ───────────────────────────────────────────────────

@router.get("/transcriptions", response_model=TaskListResponse)
async def list_transcription_tasks(
    status: Optional[str] = Query(None, description="Filter: pending/processing/completed/failed/cancelled"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """列出转录任务（支持状态过滤和分页）。"""
    async with async_session() as session:
        stmt = select(TranscriptionTask)
        count_stmt = select(func.count(TranscriptionTask.id))

        if status:
            stmt = stmt.where(TranscriptionTask.status == status)
            count_stmt = count_stmt.where(TranscriptionTask.status == status)

        # Total count
        total_result = await session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Paginated results
        stmt = stmt.order_by(TranscriptionTask.created_at.desc()).offset(offset).limit(limit)
        result = await session.execute(stmt)
        tasks = result.scalars().all()

    return TaskListResponse(
        tasks=[_task_to_status(t) for t in tasks],
        total=total,
    )
