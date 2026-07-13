"""
文件上传和管理 API — 支持 MD5 秒传
"""

import hashlib
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.auth import get_api_key
from app.db import async_session
from app.db.base import Base
from app.db.session import engine
from app.models.orm_models import UploadedFile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/files", tags=["files"], dependencies=[Depends(get_api_key)])


# ── Pydantic schemas ────────────────────────────────────────────────

class FileUploadResponse(BaseModel):
    """文件上传响应"""
    file_id: str = Field(..., description="文件UUID")
    filename: str = Field(..., description="原始文件名")
    file_size: int = Field(..., description="文件大小（字节）")
    file_md5: str = Field(..., description="文件 MD5")
    duplicate: bool = Field(default=False, description="是否为秒传（文件已存在）")
    message: str = Field(default="File uploaded successfully")


class FileInfo(BaseModel):
    """文件信息"""
    file_id: str = Field(..., description="文件UUID")
    filename: str = Field(..., description="原始文件名")
    file_size: int = Field(..., description="文件大小（字节）")
    file_md5: str = Field(..., description="文件 MD5")
    content_type: Optional[str] = Field(None, description="文件MIME类型")
    created_at: str = Field(..., description="上传时间")


class FileListResponse(BaseModel):
    """文件列表响应"""
    files: list[FileInfo] = Field(..., description="文件列表")
    total: int = Field(..., description="文件总数")


class FileDeleteResponse(BaseModel):
    """文件删除响应"""
    message: str = Field(..., description="删除结果")
    file_id: str = Field(..., description="删除的文件UUID")


# ── 常量 ────────────────────────────────────────────────────────────

SUPPORTED_FORMATS = {
    # 音频
    ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma", ".opus", ".wv", ".aiff",
    # 视频
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".mpeg", ".mpg", ".3gp", ".flv", ".wmv",
}


def _validate_file_format(filename: str) -> bool:
    from pathlib import Path
    ext = Path(filename).suffix.lower()
    return ext in SUPPORTED_FORMATS


def _compute_md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


# ── 上传 ────────────────────────────────────────────────────────────

@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(..., description="要上传的音视频文件"),
    file_md5: Optional[str] = Query(None, description="客户端计算的 MD5（可选，传入则用于秒传）"),
    file_size: Optional[int] = Query(None, description="文件大小（字节，可选）"),
):
    """
    上传音视频文件，支持 MD5 秒传。

    秒传逻辑：
    1. 客户端可在 query 中传入 `file_md5`（MD5）和 `file_size`（字节数）
    2. 服务端查询数据库：若已存在相同 MD5 + 大小的文件，直接返回已有 file_id（秒传）
    3. 若不存在，则保存文件并写入数据库

    无论是否秒传，`file_md5` 都会出现在响应中。
    """
    # 验证文件名
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    # 验证文件格式
    if not _validate_file_format(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式。支持的格式: {', '.join(sorted(SUPPORTED_FORMATS))}",
        )

    t_start = time.time()
    logger.info("[upload] 收到文件: %s, content_type: %s", file.filename, file.content_type)

    try:
        # 读取文件内容
        content = await file.read()
        actual_size = len(content)
        size_mb = actual_size / (1024 * 1024)
        logger.info("[upload] 文件读取完成: %s, 大小: %.2f MB (%d bytes)", file.filename, size_mb, actual_size)

        # 验证文件大小（最大 2GB）
        max_size = 2 * 1024 * 1024 * 1024
        if actual_size > max_size:
            raise HTTPException(status_code=400, detail="文件大小超过限制（最大 2GB）")

        # 计算实际 MD5
        actual_md5 = _compute_md5(content)

        # 如果客户端传了 file_size 且与实际不符，拒绝
        if file_size is not None and file_size != actual_size:
            raise HTTPException(status_code=400, detail=f"file_size 参数({file_size})与实际文件大小({actual_size})不匹配")

        # ── 秒传检查 ────────────────────────────────────────────
        async with async_session() as session:
            stmt = select(UploadedFile).where(
                UploadedFile.file_md5 == actual_md5,
                UploadedFile.file_size == actual_size,
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                elapsed = time.time() - t_start
                logger.info(
                    "[upload] 秒传命中: %s -> 已有 file_id=%s, 耗时: %.3fs",
                    file.filename, existing.file_id, elapsed,
                )
                return FileUploadResponse(
                    file_id=existing.file_id,
                    filename=existing.filename,
                    file_size=existing.file_size,
                    file_md5=actual_md5,
                    duplicate=True,
                    message="File already exists (instant upload)",
                )

            # ── 新文件：保存到磁盘 ──────────────────────────────
            from pathlib import Path
            import uuid as _uuid

            upload_dir = Path("./uploads")
            upload_dir.mkdir(parents=True, exist_ok=True)

            file_id = str(_uuid.uuid4())
            file_ext = Path(file.filename).suffix
            saved_filename = f"{file_id}{file_ext}"
            file_path = upload_dir / saved_filename

            with open(file_path, "wb") as f:
                f.write(content)

            # ── 写入数据库 ──────────────────────────────────────
            record = UploadedFile(
                file_id=file_id,
                filename=file.filename,
                file_size=actual_size,
                file_md5=actual_md5,
                storage_path=str(file_path),
                content_type=file.content_type or "application/octet-stream",
            )
            session.add(record)
            await session.commit()

            elapsed = time.time() - t_start
            logger.info(
                "[upload] 新文件上传成功: %s -> file_id=%s, md5=%s, 耗时: %.2fs",
                file.filename, file_id, actual_md5, elapsed,
            )

            return FileUploadResponse(
                file_id=file_id,
                filename=file.filename,
                file_size=actual_size,
                file_md5=actual_md5,
                duplicate=False,
                message="File uploaded successfully",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("文件上传失败: %s", e)
        raise HTTPException(status_code=500, detail=f"文件上传失败: {e}")


# ── 查询 ────────────────────────────────────────────────────────────

@router.get("/list", response_model=FileListResponse)
async def list_files():
    """列出所有已上传的文件"""
    async with async_session() as session:
        result = await session.execute(select(UploadedFile).order_by(UploadedFile.created_at.desc()))
        records = result.scalars().all()

    file_list = [
        FileInfo(
            file_id=r.file_id,
            filename=r.filename,
            file_size=r.file_size,
            file_md5=r.file_md5,
            content_type=r.content_type,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in records
    ]
    return FileListResponse(files=file_list, total=len(file_list))


@router.get("/{file_id}", response_model=FileInfo)
async def get_file_info(file_id: str):
    """获取指定文件的信息"""
    async with async_session() as session:
        result = await session.execute(
            select(UploadedFile).where(UploadedFile.file_id == file_id)
        )
        record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileInfo(
        file_id=record.file_id,
        filename=record.filename,
        file_size=record.file_size,
        file_md5=record.file_md5,
        content_type=record.content_type,
        created_at=record.created_at.isoformat() if record.created_at else "",
    )


@router.delete("/{file_id}", response_model=FileDeleteResponse)
async def delete_file(file_id: str):
    """删除指定文件（数据库记录 + 磁盘文件）"""
    async with async_session() as session:
        result = await session.execute(
            select(UploadedFile).where(UploadedFile.file_id == file_id)
        )
        record = result.scalar_one_or_none()

        if not record:
            raise HTTPException(status_code=404, detail="文件不存在")

        # 删除磁盘文件
        from pathlib import Path
        disk_path = Path(record.storage_path)
        if disk_path.exists():
            disk_path.unlink()

        # 删除数据库记录
        await session.delete(record)
        await session.commit()

    logger.info("[delete] 文件已删除: %s (ID: %s)", record.filename, file_id)
    return FileDeleteResponse(message="File deleted successfully", file_id=file_id)
