"""媒体 URL 异步下载 API。

5 个端点：
    POST   /v1/media/parse              提交 URL → 异步下载任务，返回 task_id
    GET    /v1/media/parse              列出所有任务
    GET    /v1/media/parse/{task_id}    查询单个任务状态/进度
    DELETE /v1/media/parse/{task_id}    删除记录 + 连带删 download/ 文件
    GET    /v1/media/parse/{task_id}/file   下载已完成文件到客户端
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.api.auth import get_api_key
from app.services import media_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/media",
    tags=["media"],
    dependencies=[Depends(get_api_key)],
)


# ── Pydantic schemas ────────────────────────────────────────────────

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
    platform: str | None
    format: str
    status: str
    progress: float
    title: str | None
    duration_seconds: int | None
    uploader: str | None
    file_path: str | None
    file_size: int | None
    error_message: str | None
    created_at: str
    updated_at: str | None
    completed_at: str | None


class TaskListResponse(BaseModel):
    tasks: list[TaskInfo]
    total: int


class TaskDeleteResponse(BaseModel):
    message: str
    task_id: str


# ── 工具 ────────────────────────────────────────────────────────────

def _record_to_info(r) -> TaskInfo:
    return TaskInfo(
        task_id=r.id,
        url=r.url,
        platform=r.platform,
        format=r.format,
        status=r.status,
        progress=r.progress or 0.0,
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

@router.post("/parse", response_model=ParseResponse)
async def parse_media(req: ParseRequest):
    """提交 URL，启动后台下载任务，立即返回 task_id。

    不同步等待下载完成 —— 客户端用 GET /v1/media/parse/{task_id} 轮询。
    """
    if not req.url:
        raise HTTPException(status_code=400, detail="URL cannot be empty")

    fmt = req.format.lower()
    if fmt not in ("audio", "video"):
        raise HTTPException(status_code=400, detail="format must be audio or video")

    platform = media_service.detect_platform(req.url)
    task_id = await media_service.create_parse_task(req.url, fmt)
    logger.info("[media] 收到媒体解析任务: url=%s, platform=%s, format=%s -> task_id=%s", req.url, platform, fmt, task_id)

    return ParseResponse(task_id=task_id, status="pending", platform=platform)


@router.get("/parse", response_model=TaskListResponse)
async def list_parse_tasks(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """列出所有下载任务（按创建时间倒序）。"""
    records = await media_service.list_tasks(limit=limit, offset=offset)
    logger.info("[media] 查询任务列表: total=%d, offset=%d, limit=%d", len(records), offset, limit)
    return TaskListResponse(
        tasks=[_record_to_info(r) for r in records],
        total=len(records),
    )


@router.get("/parse/{task_id}", response_model=TaskInfo)
async def get_parse_task(task_id: str):
    """查询单个任务的最新状态与进度。"""
    record = await media_service.get_task(task_id)
    if not record:
        logger.warning("[media] 任务不存在: task_id=%s", task_id)
        raise HTTPException(status_code=404, detail="Task not found")
    logger.info("[media] 查询任务状态: task_id=%s, status=%s, progress=%.1f%%",
                task_id, record.status, (record.progress or 0.0) * 100)
    return _record_to_info(record)


@router.delete("/parse/{task_id}", response_model=TaskDeleteResponse)
async def delete_parse_task(task_id: str):
    """删除任务记录 + 连带删 download/ 下文件。

    默认连文件一起删（按用户要求）。
    """
    success, msg = await media_service.delete_task(task_id)
    if not success:
        logger.warning("[media] 删除任务失败: task_id=%s, msg=%s", task_id, msg)
        raise HTTPException(status_code=404, detail=msg)
    logger.info("[media] 删除任务成功: task_id=%s, msg=%s", task_id, msg)
    return TaskDeleteResponse(message=msg, task_id=task_id)


@router.get("/parse/{task_id}/file")
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

    # 文件名展示用平台+原标题，避免 yt-dlp 内部 id 命名难读
    title = record.title or task_id
    # 清理文件名中的非法字符
    safe_title = "".join(c for c in title if c not in '/\\:*?"<>|')[:100]
    ext = disk_path.suffix
    download_name = f"{record.platform or 'media'}_{safe_title}{ext}"

    logger.info("[media] 下载解析媒体文件: task_id=%s, file=%s", task_id, download_name)
    return FileResponse(
        path=str(disk_path),
        filename=download_name,
        media_type="application/octet-stream",
    )
