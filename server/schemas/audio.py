from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, HttpUrl, Field, ConfigDict


class OutputFormat(str, Enum):
    TEXT = "text"      # 纯文本
    SRT = "srt"        # SRT 字幕格式
    VTT = "vtt"        # WebVTT 字幕格式
    JSON = "json"      # JSON 格式（含时间轴）
    VERBOSE_JSON = "verbose_json"  # 详细 JSON 格式（OpenAI 兼容）
    DIARIZED_JSON = "diarized_json"  # 说话人分离 JSON 格式


# ========== 统一请求/响应模型（参考 OpenAI 格式） ==========

class WordTimestamp(BaseModel):
    """词级别时间戳。"""
    word: str = Field(..., description="词或字")
    start: float = Field(..., description="开始时间（秒）")
    end: float = Field(..., description="结束时间（秒）")
    probability: Optional[float] = Field(None, description="置信度概率")


class Segment(BaseModel):
    """识别结果的分段。"""
    id: int = Field(0, description="分段 ID")
    start: float = Field(..., description="开始时间（秒）")
    end: float = Field(..., description="结束时间（秒）")
    text: str = Field(..., description="识别文本")
    speaker: Optional[Union[int, str]] = Field(None, description="说话人 ID (如 0, 1 或 'SPEAKER_00')")
    is_endpoint: bool = Field(False, description="是否为确定端点/完整句子")
    words: Optional[list[WordTimestamp]] = Field(None, description="词级时间戳列表")
    confidence: Optional[float] = Field(None, description="分段平均置信度")


class TranscriptionRequest(BaseModel):
    """统一的语音识别请求模型。"""
    model_config = ConfigDict(populate_by_name=True)

    url: Optional[HttpUrl] = Field(None, description="音视频 URL（与 file 二选一）")
    model: Optional[str] = Field(None, alias="engine", description="引擎名称")
    language: Optional[str] = Field(None, description="语言代码（如 zh、en、auto）")
    response_format: OutputFormat = Field(OutputFormat.JSON, description="输出格式")
    prompt: Optional[str] = Field(None, description="提示词（可选）")
    word_timestamps: bool = Field(True, description="是否提取词级时间戳")
    vad_filter: bool = Field(True, description="是否启用 VAD 过滤背景噪音")
    resegment: bool = Field(True, description="是否根据断句与标点优化字幕切片")
    max_line_length: int = Field(30, description="单行字幕最大字符数")
    max_segment_duration: float = Field(6.0, description="单个字幕切片最大时长（秒）")


class TranscriptionResponse(BaseModel):
    """统一的语音识别响应模型。"""
    text: str = Field(..., description="识别的完整文本")
    segments: list[Segment] = Field(default_factory=list, description="分段结果")
    language: Optional[str] = Field(None, description="检测到的语言")
    duration: Optional[float] = Field(None, description="音频时长（秒）")
    engine: str = Field(..., description="使用的引擎")


# ========== 兼容旧接口模型 ==========

class FileRequest(BaseModel):
    """旧的文件请求模型（兼容）。"""
    url: Optional[HttpUrl] = None
    engine: Optional[str] = None
    format: OutputFormat = OutputFormat.TEXT


class FileResponse(BaseModel):
    """旧的文件响应模型（兼容）。"""
    text: str
    segments: list[Segment]
    language: Optional[str] = None
    duration: Optional[float] = None
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
