from enum import Enum

from pydantic import BaseModel, HttpUrl


class OutputFormat(str, Enum):
    TEXT = "text"      # 纯文本
    SRT = "srt"        # SRT 字幕格式
    VTT = "vtt"        # WebVTT 字幕格式
    JSON = "json"      # JSON 格式（含时间轴）
    TSV = "tsv"        # TSV 格式（制表符分隔）


class FileRequest(BaseModel):
    url: HttpUrl | None = None
    engine: str | None = None
    format: OutputFormat = OutputFormat.TEXT


class Segment(BaseModel):
    start: float
    end: float
    text: str


class FileResponse(BaseModel):
    text: str
    segments: list[Segment]
    language: str | None = None
    duration: float | None = None
    engine: str
    format: str


class StreamResponse(BaseModel):
    text: str
    is_final: bool


class StreamLine(BaseModel):
    """流式识别中的一行已确认文本，包含时间戳和说话人信息。"""
    speaker: int = 1
    text: str
    start: str = ""
    end: str = ""


class WLKStreamResponse(BaseModel):
    """WhisperLiveKit 风格的流式识别响应。"""
    status: str = "active_transcription"  # active_transcription / no_audio_detected / error
    lines: list[StreamLine] = []
    buffer_transcription: str = ""
    buffer_diarization: str = ""
    buffer_translation: str = ""
    error: str = ""
