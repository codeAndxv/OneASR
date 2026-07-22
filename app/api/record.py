"""转录记录查询 API。"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import asc, desc, func, select, text

from app.api.auth import get_api_key
from app.db import async_session
from app.models.orm_models import FileTranscriptionRecord, StreamingRecord, UploadedFile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/records", tags=["records"], dependencies=[Depends(get_api_key)])


# ── Schemas ──────────────────────────────────────────────────────

class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 20
    sort_by: str = "created_at"
    sort_order: str = "desc"  # asc / desc


class PaginatedResponse(BaseModel):
    items: list[dict]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Helpers ──────────────────────────────────────────────────────

def _row_to_dict(row) -> dict:
    d = {c.key: getattr(row, c.key) for c in row.__table__.columns}
    for k, v in d.items():
        if isinstance(v, datetime):
            # 确保所有 datetime 带时区信息，前端 new Date() 才能正确转本地时间
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            d[k] = v.isoformat()
    return d


# ── Upload Records ───────────────────────────────────────────────

@router.get("/uploads", response_model=PaginatedResponse)
async def list_upload_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at", pattern="^(created_at|filename|file_size)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
):
    """分页列出上传文件记录。"""
    sort_col = getattr(UploadedFile, sort_by)
    order = desc(sort_col) if sort_order == "desc" else asc(sort_col)

    async with async_session() as session:
        total = (await session.execute(select(func.count(UploadedFile.id)))).scalar_one()
        result = await session.execute(
            select(UploadedFile).order_by(order).offset((page - 1) * page_size).limit(page_size)
        )
        items = [_row_to_dict(r) for r in result.scalars().all()]

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size, total_pages=total_pages,
    )


# ── File Transcription Records ──────────────────────────────────

@router.get("/file-transcriptions", response_model=PaginatedResponse)
async def list_file_transcription_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at", pattern="^(created_at|filename|engine_name|total_time|is_completed)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
):
    """分页列出文件转录记录。"""
    sort_col = getattr(FileTranscriptionRecord, sort_by)
    order = desc(sort_col) if sort_order == "desc" else asc(sort_col)

    async with async_session() as session:
        total = (await session.execute(select(func.count(FileTranscriptionRecord.id)))).scalar_one()
        result = await session.execute(
            select(FileTranscriptionRecord).order_by(order).offset((page - 1) * page_size).limit(page_size)
        )
        items = [_row_to_dict(r) for r in result.scalars().all()]

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size, total_pages=total_pages,
    )


# ── Streaming Records ───────────────────────────────────────────

@router.get("/streaming", response_model=PaginatedResponse)
async def list_streaming_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at", pattern="^(created_at|engine_name|total_time|is_completed)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
):
    """分页列出流式识别记录。"""
    sort_col = getattr(StreamingRecord, sort_by)
    order = desc(sort_col) if sort_order == "desc" else asc(sort_col)

    async with async_session() as session:
        total = (await session.execute(select(func.count(StreamingRecord.id)))).scalar_one()
        result = await session.execute(
            select(StreamingRecord).order_by(order).offset((page - 1) * page_size).limit(page_size)
        )
        items = [_row_to_dict(r) for r in result.scalars().all()]

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size, total_pages=total_pages,
    )
