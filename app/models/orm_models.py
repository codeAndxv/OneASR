"""ORM 数据模型定义。"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

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


class FileTranscriptionRecord(Base):
    """文件转录记录"""
    __tablename__ = "file_transcription_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_id = Column(String(36), unique=True, nullable=False, index=True, comment="记录 UUID")
    filename = Column(String(512), nullable=False, comment="原始文件名")
    file_size = Column(Integer, nullable=True, comment="文件大小（字节）")
    engine_name = Column(String(64), nullable=False, comment="使用的引擎名称")
    model_name = Column(String(64), nullable=True, comment="使用的模型名称")
    device_info = Column(String(64), nullable=True, comment="计算设备（cpu/cuda）")
    language = Column(String(16), nullable=True, comment="识别语言")
    response_format = Column(String(16), nullable=True, comment="输出格式")
    segment_count = Column(Integer, nullable=True, comment="识别段落数")
    result_length = Column(Integer, nullable=True, comment="结果文本长度（字符）")
    total_time = Column(Float, nullable=True, comment="转录总耗时（秒）")
    is_completed = Column(Boolean, default=False, nullable=False, comment="是否完成")
    error_message = Column(Text, nullable=True, comment="失败信息")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    created_at = Column(DateTime, default=datetime.utcnow, comment="请求时间")


class StreamingRecord(Base):
    """流式语音识别记录"""
    __tablename__ = "streaming_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_id = Column(String(36), unique=True, nullable=False, index=True, comment="记录 UUID")
    engine_name = Column(String(64), nullable=False, comment="使用的引擎名称")
    model_name = Column(String(64), nullable=True, comment="使用的模型名称")
    language = Column(String(16), nullable=True, comment="识别语言")
    line_count = Column(Integer, nullable=True, comment="确认的文本行数")
    total_time = Column(Float, nullable=True, comment="会话总耗时（秒）")
    is_completed = Column(Boolean, default=False, nullable=False, comment="是否完成")
    error_message = Column(Text, nullable=True, comment="失败信息")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    created_at = Column(DateTime, default=datetime.utcnow, comment="连接时间")
