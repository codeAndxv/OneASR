"""已上传文件读取服务 — 抽离自 audio.py。"""

import logging
from pathlib import Path

from sqlalchemy import select

from app.db import async_session
from app.models.orm_models import UploadedFile

logger = logging.getLogger(__name__)


class UploadedFileInfo:
    """上传文件的元数据 + 磁盘读取。"""
    __slots__ = ("file_id", "filename", "file_size", "storage_path")

    def __init__(self, file_id: str, filename: str, file_size: int, storage_path: str):
        self.file_id = file_id
        self.filename = filename
        self.file_size = file_size
        self.storage_path = storage_path

    def read_bytes(self) -> bytes:
        p = Path(self.storage_path)
        if not p.exists():
            raise FileNotFoundError(f"文件已丢失: {self.storage_path}")
        return p.read_bytes()


async def get_uploaded_file(file_id: str) -> UploadedFileInfo | None:
    """根据 file_id 查询已上传文件的元数据。"""
    async with async_session() as session:
        result = await session.execute(
            select(UploadedFile).where(UploadedFile.file_id == file_id)
        )
        record = result.scalar_one_or_none()
    if record is None:
        return None
    return UploadedFileInfo(
        file_id=record.file_id,
        filename=record.filename,
        file_size=record.file_size,
        storage_path=record.storage_path,
    )
