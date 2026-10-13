"""OneASR Extended async audio transcriptions API (/v1/x/audio/transcriptions).

Supports large audio/video files up to 2 GB and hours-long transcription tasks.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from server.api.auth import get_api_key
from server.schemas.transcription import (
    TaskCancelResponse,
    TaskCreateRequest,
    TaskCreateResponse,
    TaskListResponse,
    TaskStatusResponse,
)
from server.services import transcription_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/x/audio", tags=["x-audio"], dependencies=[Depends(get_api_key)])


def _to_status_response(task, segments: list[dict] | None = None) -> TaskStatusResponse:
    return TaskStatusResponse(
        task_id=task.task_id,
        status=task.status,
        progress=task.progress,
        filename=task.filename,
        file_size=task.file_size,
        source_type=task.source_type,
        model=task.model,
        language=task.language,
        response_format=task.response_format,
        total_time=task.total_time,
        segment_count=task.segment_count,
        text=task.result_text,
        segments=segments or [],
        error_message=task.error_message,
        created_at=task.created_at.isoformat() if task.created_at else "",
        updated_at=task.updated_at.isoformat() if task.updated_at else "",
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
    )


@router.post("/transcriptions", response_model=TaskCreateResponse)
async def create_transcription_task(req: TaskCreateRequest):
    """创建异步转录任务。"""
    try:
        task = await transcription_service.create_task(
            file_uuid=req.file_uuid,
            model=req.model,
            language=req.language,
            response_format=req.response_format,
            prompt=req.prompt,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("[x-audio] 创建转录任务失败: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

    return TaskCreateResponse(
        task_id=task.task_id,
        status=task.status,
        created_at=task.created_at.isoformat(),
    )


@router.get("/transcriptions", response_model=TaskListResponse)
async def list_transcription_tasks(
    status: Optional[str] = Query(None, description="Filter: pending/processing/completed/failed/cancelled"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """列出转录任务列表（支持状态过滤与分页）。"""
    tasks, total = await transcription_service.list_tasks(status=status, limit=limit, offset=offset)
    return TaskListResponse(
        tasks=[_to_status_response(t) for t in tasks],
        total=total,
    )


@router.get("/transcriptions/{task_id}", response_model=TaskStatusResponse)
async def get_transcription_task(task_id: str):
    """查询单个任务状态与已识别的分段结果。"""
    task, segments = await transcription_service.get_task_with_segments(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return _to_status_response(task, segments)


@router.get("/transcriptions/{task_id}/stream")
async def stream_transcription_result(task_id: str):
    """通过 SSE 订阅异步任务的实时识别结果与进度流。"""
    task, _ = await transcription_service.get_task_with_segments(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    if task.status == "failed":
        raise HTTPException(status_code=500, detail=f"Task failed: {task.error_message}")
    if task.status == "cancelled":
        raise HTTPException(status_code=410, detail="Task was cancelled")

    stream_gen = transcription_service.generate_task_sse_stream(task_id)
    return StreamingResponse(stream_gen, media_type="text/event-stream")


@router.delete("/transcriptions/{task_id}", response_model=TaskCancelResponse)
async def cancel_transcription_task(task_id: str):
    """取消转录任务（仅 pending / processing 状态可取消）。"""
    success, reason = await transcription_service.cancel_task(task_id)
    if not success:
        if reason == "not_found":
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        else:
            raise HTTPException(status_code=400, detail=reason)

    return TaskCancelResponse(message="Task cancelled", task_id=task_id)
