"""ORM 数据模型定义。"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

from app.db.base import Base


def _utcnow():
    return datetime.now(timezone.utc)


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(36), unique=True, nullable=False, index=True, comment="UUID")
    filename = Column(String(512), nullable=False, comment="原始文件名")
    file_size = Column(Integer, nullable=False, comment="文件大小（字节）")
    file_md5 = Column(String(32), nullable=False, index=True, comment="文件 MD5")
    storage_path = Column(String(1024), nullable=False, comment="磁盘存储路径")
    content_type = Column(String(128), nullable=True, comment="MIME 类型")
    created_at = Column(DateTime(timezone=True), default=_utcnow, comment="上传时间")


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
    completed_at = Column(DateTime(timezone=True), nullable=True, comment="完成时间")
    created_at = Column(DateTime(timezone=True), default=_utcnow, comment="请求时间")


class MediaParseRecord(Base):
    """媒体 URL 异步下载任务记录 —— 抖音/TikTok/B站/YouTube 等。

    一条记录 = 一个下载任务 = 一份下载完成的本地媒体文件。
    `id` 同时作为 task_id 和 media_id 使用。
    """
    __tablename__ = "media_parse_records"

    id = Column(String(36), primary_key=True, comment="UUID，同时作为 task_id 与 media_id")
    url = Column(String(2048), nullable=False, index=True, comment="原始 URL")
    platform = Column(String(32), nullable=True, comment="平台：douyin/tiktok/bilibili/youtube/unknown")
    format = Column(String(16), nullable=False, default="audio", comment="下载格式：audio/video")

    status = Column(String(16), nullable=False, default="pending", index=True,
                    comment="任务状态：pending/running/succeeded/failed")
    progress = Column(Float, nullable=False, default=0.0, comment="下载进度 0.0~1.0")

    title = Column(String(512), nullable=True, comment="媒体标题")
    duration_seconds = Column(Integer, nullable=True, comment="媒体时长（秒）")
    uploader = Column(String(256), nullable=True, comment="上传者/作者")

    file_path = Column(String(1024), nullable=True, comment="成功后的本地相对路径")
    file_size = Column(Integer, nullable=True, comment="文件大小（字节）")
    file_id = Column(String(36), nullable=True, index=True, comment="注册到 uploaded_files 后的 UUID")
    error_message = Column(Text, nullable=True, comment="失败信息")

    created_at = Column(DateTime(timezone=True), default=_utcnow, comment="提交时间")
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, comment="状态更新时间")
    completed_at = Column(DateTime(timezone=True), nullable=True, comment="下载完成时间")


class TranscriptionTask(Base):
    """异步转录任务 — 支持大文件（≤2GB）长时间转录。"""
    __tablename__ = "transcription_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(36), unique=True, nullable=False, index=True, comment="任务 UUID")

    # ── 状态 ──────────────────────────────────────────────────────
    status = Column(String(16), nullable=False, default="pending", index=True,
                    comment="pending / processing / completed / failed / cancelled")
    progress = Column(Float, nullable=False, default=0.0, comment="进度 0.0~1.0")

    # ── 文件来源（三选一）────────────────────────────────────────
    source_type = Column(String(16), nullable=False, comment="file / file_url / file_uuid")
    filename = Column(String(512), nullable=False, comment="原始文件名")
    file_size = Column(Integer, nullable=True, comment="文件大小（字节）")
    file_url = Column(String(2048), nullable=True, comment="音频文件 URL（source_type=file_url 时）")
    file_uuid = Column(String(36), nullable=True, comment="已上传文件 UUID（source_type=file_uuid 时）")

    # ── 转录参数 ─────────────────────────────────────────────────
    model = Column(String(64), nullable=False, comment="模型标识 (engine_name/model_name)")
    language = Column(String(16), nullable=True, comment="语言代码 (ISO-639-1)")
    response_format = Column(String(16), nullable=True, default="json", comment="输出格式")

    # ── 结果 ─────────────────────────────────────────────────────
    result_text = Column(Text, nullable=True, comment="完整转录文本")
    result_duration = Column(Float, nullable=True, comment="音频时长（秒）")
    segment_count = Column(Integer, nullable=True, comment="识别段落数")

    # ── 引擎信息 ─────────────────────────────────────────────────
    device_info = Column(String(64), nullable=True, comment="计算设备 (cpu/cuda)")

    # ── 错误 ─────────────────────────────────────────────────────
    error_message = Column(Text, nullable=True, comment="失败信息")

    # ── 时间 ─────────────────────────────────────────────────────
    total_time = Column(Float, nullable=True, comment="转录总耗时（秒）")
    created_at = Column(DateTime(timezone=True), default=_utcnow, comment="创建时间")
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, comment="更新时间")
    completed_at = Column(DateTime(timezone=True), nullable=True, comment="完成时间")


class TranscriptionSegment(Base):
    """转录任务的分段结果 — 实时写入，支持流式消费。"""
    __tablename__ = "transcription_segments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(36), nullable=False, index=True, comment="关联任务 UUID")
    segment_index = Column(Integer, nullable=False, comment="段落序号（从 0 开始）")
    start = Column(Float, nullable=False, comment="开始时间（秒）")
    end = Column(Float, nullable=False, comment="结束时间（秒）")
    text = Column(Text, nullable=False, comment="识别文本")
    created_at = Column(DateTime(timezone=True), default=_utcnow, comment="写入时间")


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
    completed_at = Column(DateTime(timezone=True), nullable=True, comment="完成时间")
    created_at = Column(DateTime(timezone=True), default=_utcnow, comment="连接时间")
