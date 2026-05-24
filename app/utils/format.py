"""输出格式转换工具。"""

from enum import Enum

from app.models.schemas import Segment


class OutputFormat(str, Enum):
    TEXT = "text"      # 纯文本
    SRT = "srt"        # SRT 字幕格式
    VTT = "vtt"        # WebVTT 字幕格式
    JSON = "json"      # JSON 格式（含时间轴）
    TSV = "tsv"        # TSV 格式（制表符分隔）


def format_time_srt(seconds: float) -> str:
    """SRT 时间格式: HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def format_time_vtt(seconds: float) -> str:
    """VTT 时间格式: HH:MM:SS.mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def to_text(text: str, _segments: list[Segment]) -> str:
    return text


def to_srt(_text: str, segments: list[Segment]) -> str:
    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{format_time_srt(seg.start)} --> {format_time_srt(seg.end)}")
        lines.append(seg.text)
        lines.append("")
    return "\n".join(lines)


def to_vtt(_text: str, segments: list[Segment]) -> str:
    lines = ["WEBVTT", ""]
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{format_time_vtt(seg.start)} --> {format_time_vtt(seg.end)}")
        lines.append(seg.text)
        lines.append("")
    return "\n".join(lines)


def to_json(text: str, segments: list[Segment]) -> str:
    import json
    data = {
        "text": text,
        "segments": [seg.model_dump() for seg in segments],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def to_tsv(_text: str, segments: list[Segment]) -> str:
    lines = ["start\tend\ttext"]
    for seg in segments:
        lines.append(f"{seg.start:.3f}\t{seg.end:.3f}\t{seg.text}")
    return "\n".join(lines)


_formatters = {
    OutputFormat.TEXT: to_text,
    OutputFormat.SRT: to_srt,
    OutputFormat.VTT: to_vtt,
    OutputFormat.JSON: to_json,
    OutputFormat.TSV: to_tsv,
}


def format_output(text: str, segments: list[Segment], fmt: OutputFormat | str) -> str:
    """将识别结果转换为指定格式。"""
    if isinstance(fmt, str):
        fmt = OutputFormat(fmt)
    formatter = _formatters.get(fmt)
    if not formatter:
        raise ValueError(f"不支持的格式: {fmt}，可用: {list(OutputFormat)}")
    return formatter(text, segments)
