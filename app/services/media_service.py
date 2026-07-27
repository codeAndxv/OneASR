"""媒体 URL 异步下载服务 —— 后台任务调度 + 状态机 + 数据库读写。

状态机：
    pending → running → succeeded
                    └── → failed

后台任务用 asyncio.create_task 进程内调度，与 FastAPI 同进程。
重启时 audio.py lifespan 调用 reset_stale_tasks() 把还挂在 pending/running 的标 failed。
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, update

from app.db import async_session
from app.models.orm_models import MediaParseRecord
from app.utils.video_url import (
    DOWNLOAD_DIR,
    download_video,
    extract_info,
    detect_platform,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── 任务创建与后台执行 ────────────────────────────────────────────

async def create_parse_task(url: str, fmt: str) -> str:
    """创建一条 pending 记录，立即返回 task_id。后台下载异步进行。

    fmt: "audio" 或 "video"
    """
    task_id = str(uuid.uuid4())
    platform = detect_platform(url)

    async with async_session() as session:
        record = MediaParseRecord(
            id=task_id,
            url=url,
            platform=platform,
            format=fmt,
            status="pending",
            progress=0.0,
        )
        session.add(record)
        await session.commit()

    logger.info("[media] 创建下载任务: task_id=%s platform=%s format=%s url=%s",
                task_id, platform, fmt, url)

    # 投递后台协程 —— 不等待
    asyncio.create_task(_run_download(task_id, url, fmt == "video"))

    return task_id


async def _run_download(task_id: str, url: str, video_format: bool) -> None:
    """后台下载协程：先 extract_info 预解析写元数据，再实际下载。

    所有失败都捕获并写入 error_message，任务最终 status 一定收敛到 succeeded/failed。
    """
    try:
        await _update(task_id, status="running", progress=0.0)

        # 1) 预解析元数据（廉价，不下载本体）
        info = await extract_info(url)
        await _update(
            task_id,
            title=info.title or None,
            duration_seconds=info.duration_seconds,
            uploader=info.uploader,
        )

        # 2) 实际下载（audio 或 video），progress_hook 实时回写进度
        def _hook(d: dict) -> None:
            # 同步回调在 to_thread 的工作线程里跑，DB 是异步的 —— 用 ensure_future 投递
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                pct = (downloaded / total) if total else 0.0
                asyncio.ensure_future(_update(task_id, progress=pct))
            elif d.get("status") == "finished":
                asyncio.ensure_future(_update(task_id, progress=1.0))

        video_info, file_path, file_size = await download_video(
            url,
            audio_only=not video_format,
            progress_hook=_hook,
        )
        await _update_video_info(task_id, video_info)

        # 3) 写完成态
        await _update(
            task_id,
            status="succeeded",
            progress=1.0,
            file_path=file_path,
            file_size=file_size,
            completed_at=_utcnow(),
        )
        logger.info("[media] 下载成功: task_id=%s path=%s size=%d",
                    task_id, file_path, file_size)

    except Exception as e:
        logger.warning("[media] 下载失败: task_id=%s error=%s", task_id, e)
        await _update(
            task_id,
            status="failed",
            error_message=str(e),
            completed_at=_utcnow(),
        )


# ── DB 读写辅助 ────────────────────────────────────────────────────

async def _update(task_id: str, **fields) -> None:
    """局部字段更新。"""
    if not fields:
        return
    fields["updated_at"] = _utcnow()
    async with async_session() as session:
        await session.execute(
            update(MediaParseRecord)
            .where(MediaParseRecord.id == task_id)
            .values(**fields)
        )
        await session.commit()


async def _update_video_info(task_id: str, info) -> None:
    """下载成功后同步视频元数据（避免预解析失败时元数据为空）。"""
    await _update(
        task_id,
        title=info.title or None,
        duration_seconds=info.duration_seconds,
        uploader=info.uploader,
    )


async def get_task(task_id: str) -> MediaParseRecord | None:
    async with async_session() as session:
        result = await session.execute(
            select(MediaParseRecord).where(MediaParseRecord.id == task_id)
        )
        return result.scalar_one_or_none()


async def list_tasks(limit: int = 50, offset: int = 0) -> list[MediaParseRecord]:
    async with async_session() as session:
        result = await session.execute(
            select(MediaParseRecord)
            .order_by(MediaParseRecord.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())


async def delete_task(task_id: str) -> tuple[bool, str]:
    """删除任务记录 + 连带删 download/ 下文件。返回 (success, message)。"""
    async with async_session() as session:
        result = await session.execute(
            select(MediaParseRecord).where(MediaParseRecord.id == task_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            return False, "任务不存在"

        # 删文件（成功任务才有 file_path）
        file_deleted = False
        if record.file_path:
            disk_path = Path(record.file_path)
            if disk_path.exists():
                disk_path.unlink()
                file_deleted = True
                logger.info("[media] 删除文件: %s", disk_path)

        await session.delete(record)
        await session.commit()

    return True, "已删除" + ("（含文件）" if file_deleted else "（无文件）")


async def reset_stale_tasks() -> int:
    """启动清洗：把所有 pending/running 任务标 failed（避免重启后任务卡死）。"""
    async with async_session() as session:
        result = await session.execute(
            update(MediaParseRecord)
            .where(MediaParseRecord.status.in_(["pending", "running"]))
            .values(status="failed", error_message="服务重启", updated_at=_utcnow())
        )
        await session.commit()
        return result.rowcount or 0
