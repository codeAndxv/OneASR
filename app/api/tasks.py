"""Async transcription tasks API — upload → create → poll → result.

Supports files up to 2 GB and long-running transcriptions (hours).

Endpoints:
  POST   /v1/tasks/transcriptions                Create a transcription task
  GET    /v1/tasks/transcriptions                 List tasks (with filters)
  GET    /v1/tasks/transcriptions/{task_id}       Get task status
  GET    /v1/tasks/transcriptions/{task_id}/result Get transcription result
  DELETE /v1/tasks/transcriptions/{task_id}       Cancel a task
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
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select, func

from app.api.auth import get_api_key
from app.core.config import app_config
from app.db import async_session
from app.engines.registry import get_engine
from app.models.orm_models import TranscriptionTask
from app.services.file_service import get_uploaded_file
from app.utils.audio import convert_to_wav

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/tasks", tags=["tasks"], dependencies=[Depends(get_api_key)])

MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB
MAX_URL_DOWNLOAD_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB
NATIVE_AUDIO_FORMATS = {".wav"}


# ── Pydantic response models ─────────────────────────────────────

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
    error_message: Optional[str] = None
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None


class TaskResultResponse(BaseModel):
    text: str
    segments: list[dict] = Field(default_factory=list)
    language: Optional[str] = None
    duration: Optional[float] = None
    segment_count: Optional[int] = None
    total_time: Optional[float] = None


class TaskListResponse(BaseModel):
    tasks: list[TaskStatusResponse]
    total: int


class TaskCancelResponse(BaseModel):
    message: str
    task_id: str


# ── Helpers ──────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _task_to_status(t: TranscriptionTask) -> TaskStatusResponse:
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
    """Background coroutine: load audio → transcribe → persist result."""
    async with async_session() as session:
        # Load task
        result = await session.execute(
            select(TranscriptionTask).where(TranscriptionTask.task_id == task_id)
        )
        task = result.scalar_one_or_none()
        if task is None:
            logger.error("[tasks][%s] 任务不存在", task_id)
            return

        # Mark processing
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
                raise FileNotFoundError(f"文件不存在: {task.file_uuid}")
            data = info.read_bytes()
            filename = info.filename
            task.file_size = len(data)

        else:  # file — stored in temp during create; reload from uploads dir
            import glob as _glob
            pattern = f"./uploads/{task.file_uuid}.*"
            matches = _glob.glob(pattern)
            if not matches:
                raise FileNotFoundError(f"文件不存在: {task.file_uuid}")
            storage_path = Path(matches[0])
            data = storage_path.read_bytes()
            task.file_size = len(data)

        # Enforce size limit
        size_mb = len(data) / (1024 * 1024)
        if len(data) > MAX_FILE_SIZE:
            raise ValueError(f"文件大小 {size_mb:.1f}MB 超过限制（最大 2GB）")

        logger.info("[tasks][%s] 音频就绪: %s, %.2f MB", rid, filename, size_mb)

        # 2. Ensure WAV
        data = _ensure_wav(data, filename, rid)
        logger.info("[tasks][%s] WAV 转换完成", rid)

        # 3. Get engine
        eng = get_engine(task.model)
        logger.info("[tasks][%s] 引擎就绪: %s", rid, task.model)

        # Update progress
        async with async_session() as session:
            result = await session.execute(
                select(TranscriptionTask).where(TranscriptionTask.task_id == task_id)
            )
            t = result.scalar_one_or_none()
            if t:
                t.progress = 0.1
                t.updated_at = datetime.now(timezone.utc)
                await session.commit()

        # 4. Transcribe
        t_recog = time.time()
        text, segments = await eng.transcribe_file(data)
        recog_time = time.time() - t_recog
        total_time = time.time() - t_start

        duration = segments[-1].end if segments else 0.0
        segments_json = json.dumps(
            [{"id": i, "start": s.start, "end": s.end, "text": s.text} for i, s in enumerate(segments)],
            ensure_ascii=False,
        )

        logger.info("[tasks][%s] 转录完成: %d 段, %d 字符, %.2fs",
                     rid, len(segments), len(text), recog_time)

        # 5. Persist result
        async with async_session() as session:
            result = await session.execute(
                select(TranscriptionTask).where(TranscriptionTask.task_id == task_id)
            )
            t = result.scalar_one_or_none()
            if t:
                t.status = "completed"
                t.progress = 1.0
                t.result_text = text
                t.result_segments = segments_json
                t.result_duration = duration
                t.segment_count = len(segments)
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
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    file_url: Optional[str] = Form(None, description="音频文件 URL"),
    file_uuid: Optional[str] = Form(None, description="已上传文件的 UUID"),
    model: str = Form(..., description="模型标识 (engine_name/model_name)"),
    language: Optional[str] = Form(None, description="语言代码 (ISO-639-1)"),
    response_format: str = Form("json", description="输出格式"),
):
    """创建异步转录任务。

    file / file_url / file_uuid 三选一，优先级: file > file_url > file_uuid。
    文件上限 2GB，适用于大文件和长时间转录。
    """
    task_id = str(uuid.uuid4())
    rid = task_id[:8]
    now = datetime.now(timezone.utc)

    # Determine source and filename
    source_type = ""
    filename = "unknown"
    file_size: int | None = None
    saved_file_uuid: str | None = None

    if file:
        source_type = "file"
        filename = file.filename or "audio.wav"
        # Save to temp storage for background worker
        content = await file.read()
        file_size = len(content)
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"文件大小超过限制: {file_size / 1024 / 1024:.1f}MB，最大 2GB")

        # Store file for background processing
        upload_dir = Path("./uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        saved_file_uuid = str(uuid.uuid4())
        ext = Path(filename).suffix or ".bin"
        file_path = upload_dir / f"{saved_file_uuid}{ext}"
        file_path.write_bytes(content)
        logger.info("[tasks][%s] 文件已保存: %s (%.2f MB)", rid, filename, file_size / 1024 / 1024)

    elif file_url:
        source_type = "file_url"
        filename = Path(file_url.split("?")[0]).name or "audio.wav"
        logger.info("[tasks][%s] URL 来源: %s", rid, file_url)

    elif file_uuid:
        source_type = "file_uuid"
        info = await get_uploaded_file(file_uuid)
        if info is None:
            raise HTTPException(status_code=404, detail=f"文件不存在: {file_uuid}")
        filename = info.filename
        file_size = info.file_size if hasattr(info, "file_size") else None
        saved_file_uuid = file_uuid
        logger.info("[tasks][%s] UUID 来源: %s (%s)", rid, file_uuid, filename)

    else:
        raise HTTPException(status_code=400, detail="必须提供 file、file_url 或 file_uuid 参数")

    # Create DB record
    async with async_session() as session:
        task = TranscriptionTask(
            task_id=task_id,
            status="pending",
            progress=0.0,
            source_type=source_type,
            filename=filename,
            file_size=file_size,
            file_url=file_url if source_type == "file_url" else None,
            file_uuid=saved_file_uuid,
            model=model,
            language=language,
            response_format=response_format,
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

    logger.info("[tasks][%s] 任务已创建: model=%s lang=%s file=%s", rid, model, language, filename)

    return TaskCreateResponse(
        task_id=task_id,
        status="pending",
        created_at=now.isoformat(),
    )


# ── Get task status ──────────────────────────────────────────────

@router.get("/transcriptions/{task_id}", response_model=TaskStatusResponse)
async def get_transcription_task(task_id: str):
    """查询转录任务状态。"""
    async with async_session() as session:
        result = await session.execute(
            select(TranscriptionTask).where(TranscriptionTask.task_id == task_id)
        )
        task = result.scalar_one_or_none()

    if task is None:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    return _task_to_status(task)


# ── Get task result ──────────────────────────────────────────────

@router.get("/transcriptions/{task_id}/result")
async def get_transcription_result(task_id: str):
    """获取转录结果（仅 completed 状态可用）。"""
    async with async_session() as session:
        result = await session.execute(
            select(TranscriptionTask).where(TranscriptionTask.task_id == task_id)
        )
        task = result.scalar_one_or_none()

    if task is None:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    if task.status == "pending" or task.status == "processing":
        raise HTTPException(status_code=202, detail=f"任务仍在处理中 (status={task.status})")

    if task.status == "failed":
        raise HTTPException(status_code=500, detail=f"任务失败: {task.error_message}")

    if task.status == "cancelled":
        raise HTTPException(status_code=410, detail="任务已取消")

    segments = json.loads(task.result_segments) if task.result_segments else []

    return TaskResultResponse(
        text=task.result_text or "",
        segments=segments,
        language=task.language,
        duration=task.result_duration,
        segment_count=task.segment_count,
        total_time=task.total_time,
    )


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
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    if task.status not in ("pending", "processing"):
        raise HTTPException(status_code=400, detail=f"任务状态为 {task.status}，无法取消")

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
