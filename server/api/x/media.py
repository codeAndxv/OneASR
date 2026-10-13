"""媒体 URL 异步下载 API (OneASR Extended /v1/x/media)。

5 个端点：
    POST   /v1/x/media              提交 URL → 异步下载任务，返回 task_id
    GET    /v1/x/media              列出所有任务
    GET    /v1/x/media/{task_id}    查询单个任务状态/进度（含已注册的 file_id）
    DELETE /v1/x/media/{task_id}    删除记录 + 连带删 download/ 文件与关联 UploadedFile
    GET    /v1/x/media/{task_id}/file   下载已完成文件到客户端
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from server.api.auth import get_api_key
from server.schemas.media import (
    ParseRequest,
    ParseResponse,
    TaskDeleteResponse,
    TaskInfo,
    TaskListResponse,
)
from server.services import media_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/x/media",
    tags=["x-media"],
    dependencies=[Depends(get_api_key)],
)


# ── 工具 ────────────────────────────────────────────────────────────

def _record_to_info(r) -> TaskInfo:
    return TaskInfo(
        task_id=r.id,
        url=r.url,
        platform=r.platform,
        format=r.format,
        status=r.status,
        progress=media_service.get_realtime_progress(r.id, r.progress or 0.0),
        file_id=r.file_id,
        title=r.title,
        duration_seconds=r.duration_seconds,
        uploader=r.uploader,
        file_path=r.file_path,
        file_size=r.file_size,
        error_message=r.error_message,
        created_at=r.created_at.isoformat() if r.created_at else "",
        updated_at=r.updated_at.isoformat() if r.updated_at else None,
        completed_at=r.completed_at.isoformat() if r.completed_at else None,
    )


# ── 端点 ────────────────────────────────────────────────────────────

@router.post("", response_model=ParseResponse)
async def parse_media(req: ParseRequest):
    """提交 URL，启动后台下载任务，立即返回 task_id。

    不同步等待下载完成 —— 客户端用 GET /v1/x/media/{task_id} 轮询。
    """
    if not req.url:
        raise HTTPException(status_code=400, detail="URL cannot be empty")

    fmt = req.format.lower().strip() if req.format else None
    if fmt and fmt not in ("audio", "video"):
        raise HTTPException(status_code=400, detail="format must be audio or video")

    platform = media_service.detect_platform(req.url)
    task_id = await media_service.create_parse_task(req.url, fmt, req.resolution)
    logger.info("[x-media] 收到媒体解析任务: url=%s, platform=%s, format=%s, resolution=%s -> task_id=%s",
                req.url, platform, fmt, req.resolution, task_id)

    return ParseResponse(task_id=task_id, status="pending", platform=platform)


@router.get("", response_model=TaskListResponse)
async def list_parse_tasks(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """列出所有下载任务（按创建时间倒序）。"""
    records = await media_service.list_tasks(limit=limit, offset=offset)
    logger.info("[x-media] 查询任务列表: total=%d, offset=%d, limit=%d", len(records), offset, limit)
    return TaskListResponse(
        tasks=[_record_to_info(r) for r in records],
        total=len(records),
    )


@router.get("/{task_id}", response_model=TaskInfo)
async def get_parse_task(task_id: str):
    """查询单个任务的最新状态与进度。"""
    record = await media_service.get_task(task_id)
    if not record:
        logger.warning("[x-media] 任务不存在: task_id=%s", task_id)
        raise HTTPException(status_code=404, detail="Task not found")
    logger.info("[x-media] 查询任务状态: task_id=%s, status=%s, progress=%.1f%%",
                task_id, record.status, (record.progress or 0.0) * 100)
    return _record_to_info(record)


@router.delete("/{task_id}", response_model=TaskDeleteResponse)
async def delete_parse_task(task_id: str):
    """删除任务记录 + 连带删 download/ 下文件。"""
    success, msg = await media_service.delete_task(task_id)
    if not success:
        logger.warning("[x-media] 删除任务失败: task_id=%s, msg=%s", task_id, msg)
        raise HTTPException(status_code=404, detail=msg)
    logger.info("[x-media] 删除任务成功: task_id=%s, msg=%s", task_id, msg)
    return TaskDeleteResponse(message=msg, task_id=task_id)


@router.get("/{task_id}/file")
async def download_parse_file(task_id: str):
    """下载已完成的文件到客户端。仅 succeeded 状态可下载。"""
    record = await media_service.get_task(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="Task not found")
    if record.status != "succeeded":
        raise HTTPException(status_code=409, detail=f"Task is not completed, current status: {record.status}")
    if not record.file_path:
        raise HTTPException(status_code=409, detail="Task has no file path")

    disk_path = Path(record.file_path)
    if not disk_path.exists():
        raise HTTPException(status_code=404, detail="File has been deleted")

    title = record.title or task_id
    safe_title = "".join(c for c in title if c not in '/\\:*?"<>|')[:100]
    ext = disk_path.suffix
    download_name = f"{record.platform or 'media'}_{safe_title}{ext}"

    logger.info("[x-media] 下载解析媒体文件: task_id=%s, file=%s", task_id, download_name)
    return FileResponse(
        path=str(disk_path),
        filename=download_name,
        media_type="application/octet-stream",
    )
