"""ORM 数据模型定义。"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.db.base import Base


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(36), unique=True, nullable=False, index=True, comment="UUID")
    filename = Column(String(512), nullable=False, comment="原始文件名")
    file_size = Column(Integer, nullable=False, comment="文件大小（字节）")
    file_md5 = Column(String(32), nullable=False, index=True, comment="文件 MD5")
    storage_path = Column(String(1024), nullable=False, comment="磁盘存储路径")
    content_type = Column(String(128), nullable=True, comment="MIME 类型")
    created_at = Column(DateTime, default=datetime.utcnow, comment="上传时间")
