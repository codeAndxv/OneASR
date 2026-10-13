"""大文件异步转录任务核心业务逻辑服务。"""

import asyncio
import json
import logging
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Optional

import httpx
from sqlalchemy import func, select

from server.core.config import app_config
from server.db import async_session
from server.db.orm_models import TranscriptionSegment, TranscriptionTask
from server.engines.registry import acquire_engine, get_engine
from server.services.file_service import get_uploaded_file
from server.utils.audio_converter import AudioConverter

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB
NATIVE_AUDIO_FORMATS = {".wav"}

# 内存中正在运行的异步任务字典，供 cancel 操作取消任务
_running_tasks: dict[str, asyncio.Task] = {}


def _ensure_wav(data: bytes, filename: str, rid: str) -> bytes:
    ext = Path(filename).suffix.lower()
    if ext in NATIVE_AUDIO_FORMATS:
        return data
    logger.info("[transcription_service][%s] 格式 %s 需要转换为 WAV", rid, ext)
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_in:
        tmp_in.write(data)
        tmp_in_path = Path(tmp_in.name)
    tmp_wav: Path | None = None
    try:
        tmp_wav = AudioConverter.convert_file_to_wav(tmp_in_path)
        return tmp_wav.read_bytes()
    finally:
        tmp_in_path.unlink(missing_ok=True)
        if tmp_wav:
            tmp_wav.unlink(missing_ok=True)


async def run_transcription(task_id: str, prompt: Optional[str] = None):
    """后台协程：加载音频 -> 流式识别 -> 增量持久化分段与进度。"""
    async with async_session() as session:
        result = await session.execute(
            select(TranscriptionTask).where(TranscriptionTask.task_id == task_id)
        )
        task = result.scalar_one_or_none()
        if task is None:
            logger.error("[transcription_service][%s] 任务不存在", task_id)
            return

        task.status = "processing"
        task.progress = 0.0
        task.updated_at = datetime.now(timezone.utc)
        await session.commit()

    t_start = time.time()
    rid = task_id[:8]

    try:
        data: bytes = b""
        filename = task.filename

        if task.source_type == "file_url":
            logger.info("[transcription_service][%s] 从 URL 下载: %s", rid, task.file_url)
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

        else:
            import glob as _glob
            pattern = f"data/uploads/{task.file_uuid}.*"
            matches = _glob.glob(pattern)
            if not matches:
                raise FileNotFoundError(f"File not found: {task.file_uuid}")
            storage_path = Path(matches[0])
            data = storage_path.read_bytes()
            task.file_size = len(data)

        size_mb = len(data) / (1024 * 1024)
        if len(data) > MAX_FILE_SIZE:
            raise ValueError(f"File size {size_mb:.1f}MB exceeds limit (maximum 2GB)")

        logger.info("[transcription_service][%s] 音频就绪: %s, %.2f MB", rid, filename, size_mb)

        data = _ensure_wav(data, filename, rid)
        total_audio_duration = AudioConverter.get_audio_duration(data)
        logger.info("[transcription_service][%s] 音频总时长: %.2fs", rid, total_audio_duration)

        eng = get_engine(task.model)
        logger.info("[transcription_service][%s] 引擎就绪: %s", rid, task.model)

        async with async_session() as session:
            result = await session.execute(
                select(TranscriptionTask).where(TranscriptionTask.task_id == task_id)
            )
            t = result.scalar_one_or_none()
            if t:
                t.progress = 0.02
                t.result_duration = total_audio_duration
                t.updated_at = datetime.now(timezone.utc)
                await session.commit()

        t_recog = time.time()
        full_text = ""
        segment_index = 0

        stream_kwargs: dict = {}
        if task.language:
            stream_kwargs["language"] = task.language
        if prompt:
            stream_kwargs["prompt"] = prompt

        with acquire_engine(task.model, engine_getter=lambda _: eng):
            async for seg in eng.transcribe_file_stream(data, **stream_kwargs):
                full_text += seg.text

                words_json = None
                if getattr(seg, "words", None):
                    words_json = json.dumps([w.model_dump() for w in seg.words], ensure_ascii=False)

                async with async_session() as session:
                    segment = TranscriptionSegment(
                        task_id=task_id,
                        segment_index=segment_index,
                        start=seg.start,
                        end=seg.end,
                        text=seg.text,
                        speaker=str(seg.speaker) if getattr(seg, "speaker", None) is not None else None,
                        words_json=words_json,
                    )
                    session.add(segment)
                    await session.commit()

                segment_index += 1

                if seg.end > 0 and total_audio_duration > 0:
                    current_prog = min(0.99, round(seg.end / total_audio_duration, 4))
                    async with async_session() as session:
                        result = await session.execute(
                            select(TranscriptionTask).where(TranscriptionTask.task_id == task_id)
                        )
                        t = result.scalar_one_or_none()
                        if t and t.status == "processing":
                            t.progress = current_prog
                            t.updated_at = datetime.now(timezone.utc)
                            await session.commit()

        recog_time = time.time() - t_recog
        total_time = time.time() - t_start

        duration = total_audio_duration if total_audio_duration > 0 else 0.0
        if duration == 0.0:
            async with async_session() as session:
                result = await session.execute(
                    select(TranscriptionSegment)
                    .where(TranscriptionSegment.task_id == task_id)
                    .order_by(TranscriptionSegment.segment_index.desc())
                    .limit(1)
                )
                last_seg = result.scalar_one_or_none()
                duration = last_seg.end if last_seg else 0.0

        logger.info("[transcription_service][%s] 转录完成: %d 段, %d 字符, %.2fs",
                     rid, segment_index, len(full_text), recog_time)

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

        logger.info("[transcription_service][%s] 结果已持久化", rid)

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
        logger.info("[transcription_service][%s] 任务已取消", rid)

    except Exception as e:
        logger.exception("[transcription_service][%s] 转录失败: %s", rid, e)
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


async def create_task(
    file_uuid: str,
    model: str,
    language: Optional[str] = None,
    response_format: Optional[str] = "json",
    prompt: Optional[str] = None,
) -> TranscriptionTask:
    """创建异步转录任务并启动后台 worker。"""
    task_id = str(uuid.uuid4())
    rid = task_id[:8]
    now = datetime.now(timezone.utc)

    info = await get_uploaded_file(file_uuid)
    if info is None:
        raise FileNotFoundError(f"File not found: {file_uuid}")

    filename = info.filename
    file_size = info.file_size if hasattr(info, "file_size") else None

    async with async_session() as session:
        task = TranscriptionTask(
            task_id=task_id,
            status="pending",
            progress=0.0,
            source_type="file_uuid",
            filename=filename,
            file_size=file_size,
            file_uuid=file_uuid,
            model=model,
            language=language,
            response_format=response_format or "json",
            created_at=now,
            updated_at=now,
        )
        session.add(task)
        await session.commit()

    async_task = asyncio.create_task(run_transcription(task_id, prompt=prompt))
    _running_tasks[task_id] = async_task

    async def _cleanup(_tid: str = task_id):
        await async_task
        _running_tasks.pop(_tid, None)
    asyncio.create_task(_cleanup())

    logger.info("[transcription_service][%s] 任务已创建: model=%s lang=%s file=%s", rid, model, language, filename)
    return task


async def get_task_with_segments(task_id: str) -> tuple[Optional[TranscriptionTask], list[dict]]:
    """获取任务详情及分段列表。"""
    async with async_session() as session:
        result = await session.execute(
            select(TranscriptionTask).where(TranscriptionTask.task_id == task_id)
        )
        task = result.scalar_one_or_none()

    if task is None:
        return None, []

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

    return task, segments


async def cancel_task(task_id: str) -> tuple[bool, str]:
    """取消任务。返回 (是否成功, 状态描述或错误说明)。"""
    async with async_session() as session:
        result = await session.execute(
            select(TranscriptionTask).where(TranscriptionTask.task_id == task_id)
        )
        task = result.scalar_one_or_none()

    if task is None:
        return False, "not_found"

    if task.status not in ("pending", "processing"):
        return False, f"Task status is {task.status}, cannot cancel"

    async_task = _running_tasks.pop(task_id, None)
    if async_task and not async_task.done():
        async_task.cancel()

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

    logger.info("[transcription_service][%s] 任务已取消: filename=%s", task_id[:8], task.filename)
    return True, "cancelled"


async def list_tasks(
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[TranscriptionTask], int]:
    """分页查询任务列表。"""
    async with async_session() as session:
        stmt = select(TranscriptionTask)
        count_stmt = select(func.count(TranscriptionTask.id))

        if status:
            stmt = stmt.where(TranscriptionTask.status == status)
            count_stmt = count_stmt.where(TranscriptionTask.status == status)

        total_result = await session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = stmt.order_by(TranscriptionTask.created_at.desc()).offset(offset).limit(limit)
        result = await session.execute(stmt)
        tasks = result.scalars().all()

    return list(tasks), total


async def generate_task_sse_stream(task_id: str) -> AsyncGenerator[str, None]:
    """生成任务的 SSE 事件流。"""
    async with async_session() as session:
        result = await session.execute(
            select(TranscriptionTask).where(TranscriptionTask.task_id == task_id)
        )
        task = result.scalar_one_or_none()

    if task is None:
        return

    if task.status == "completed":
        async with async_session() as session:
            result = await session.execute(
                select(TranscriptionSegment)
                .where(TranscriptionSegment.task_id == task_id)
                .order_by(TranscriptionSegment.segment_index)
            )
            db_segments = result.scalars().all()

        total_dur = task.result_duration or (db_segments[-1].end if db_segments else 1.0)
        for seg in db_segments:
            seg_prog = min(1.0, round(seg.end / total_dur, 4)) if total_dur > 0 else 1.0
            event = {
                "type": "transcript.text.delta",
                "delta": seg.text,
                "start": seg.start,
                "end": seg.end,
                "is_endpoint": True,
                "progress": seg_prog,
            }
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        done_event = {
            "type": "transcript.text.done",
            "text": task.result_text or "",
            "progress": 1.0,
        }
        yield f"data: {json.dumps(done_event, ensure_ascii=False)}\n\n"
        return

    last_segment_index = -1
    heartbeat_interval = 30
    last_heartbeat = time.time()

    while True:
        async with async_session() as session:
            result = await session.execute(
                select(TranscriptionTask).where(TranscriptionTask.task_id == task_id)
            )
            current_task = result.scalar_one_or_none()

        total_dur = (current_task.result_duration or 0.0) if current_task else 0.0

        async with async_session() as session:
            result = await session.execute(
                select(TranscriptionSegment)
                .where(TranscriptionSegment.task_id == task_id)
                .where(TranscriptionSegment.segment_index > last_segment_index)
                .order_by(TranscriptionSegment.segment_index)
            )
            new_segments = result.scalars().all()

        for seg in new_segments:
            if total_dur > 0:
                seg_prog = min(0.99, round(seg.end / total_dur, 4))
            elif current_task:
                seg_prog = current_task.progress
            else:
                seg_prog = 0.0

            event = {
                "type": "transcript.text.delta",
                "delta": seg.text,
                "start": seg.start,
                "end": seg.end,
                "is_endpoint": True,
                "progress": seg_prog,
            }
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            last_segment_index = seg.segment_index

        if current_task is not None:
            if current_task.status == "completed":
                done_event = {
                    "type": "transcript.text.done",
                    "text": current_task.result_text or "",
                    "progress": 1.0,
                }
                yield f"data: {json.dumps(done_event, ensure_ascii=False)}\n\n"
                break
            elif current_task.status == "failed":
                error_event = {
                    "type": "task.failed",
                    "error": current_task.error_message,
                    "progress": current_task.progress,
                }
                yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
                break
            elif current_task.status == "cancelled":
                error_event = {
                    "type": "task.failed",
                    "error": "Task cancelled",
                    "progress": current_task.progress,
                }
                yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
                break

        if time.time() - last_heartbeat > heartbeat_interval:
            yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
            last_heartbeat = time.time()

        await asyncio.sleep(0.1)
