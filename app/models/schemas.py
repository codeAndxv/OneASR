from enum import Enum
from typing import Optional

from pydantic import BaseModel, HttpUrl, Field


class OutputFormat(str, Enum):
    TEXT = "text"      # 纯文本
    SRT = "srt"        # SRT 字幕格式
    VTT = "vtt"        # WebVTT 字幕格式
    JSON = "json"      # JSON 格式（含时间轴）
    VERBOSE_JSON = "verbose_json"  # 详细 JSON 格式（OpenAI 兼容）
    TSV = "tsv"        # TSV 格式（制表符分隔）


# ========== 统一请求模型（参考 OpenAI 格式） ==========

class TranscriptionRequest(BaseModel):
    """统一的语音识别请求模型。"""
    url: Optional[HttpUrl] = Field(None, description="音视频 URL（与 file 二选一）")
    model: Optional[str] = Field(None, alias="engine", description="引擎名称")
    language: Optional[str] = Field(None, description="语言代码（如 zh、en、auto）")
    response_format: OutputFormat = Field(OutputFormat.JSON, description="输出格式")
    prompt: Optional[str] = Field(None, description="提示词（可选）")

    class Config:
        populate_by_name = True


class TranscriptionResponse(BaseModel):
    """统一的语音识别响应模型。"""
    text: str = Field(..., description="识别的完整文本")
    segments: list["Segment"] = Field(default_factory=list, description="分段结果")
    language: Optional[str] = Field(None, description="检测到的语言")
    duration: Optional[float] = Field(None, description="音频时长（秒）")
    engine: str = Field(..., description="使用的引擎")


class Segment(BaseModel):
    """识别结果的分段。"""
    id: int = Field(0, description="分段 ID")
    start: float = Field(..., description="开始时间（秒）")
    end: float = Field(..., description="结束时间（秒）")
    text: str = Field(..., description="识别文本")
    speaker: Optional[int] = Field(None, description="说话人 ID")


# ========== 旧模型（保持兼容） ==========

class FileRequest(BaseModel):
    """旧的文件请求模型（兼容）。"""
    url: HttpUrl | None = None
    engine: str | None = None
    format: OutputFormat = OutputFormat.TEXT


class FileResponse(BaseModel):
    """旧的文件响应模型（兼容）。"""
    text: str
    segments: list[Segment]
    language: str | None = None
    duration: float | None = None
    engine: str
    format: str


class StreamResponse(BaseModel):
    """流式识别响应。"""
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


# 解决前向引用
TranscriptionResponse.model_rebuild()
