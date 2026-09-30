"""基于 silero-vad 的音频切分工具。"""

import subprocess
import tempfile
from pathlib import Path

import numpy as np
import torch


def load_audio_with_ffmpeg(audio_path: str | Path, sample_rate: int = 16000) -> torch.Tensor:
    """使用 ffmpeg 加载音频并转换为指定采样率。"""
    result = subprocess.run(
        [
            "ffmpeg", "-i", str(audio_path),
            "-ar", str(sample_rate),
            "-ac", "1",
            "-f", "f32le",
            "-acodec", "pcm_f32le",
            "pipe:1",
        ],
        capture_output=True,
        check=True,
    )
    # 将原始字节转换为 numpy 数组，再转为 tensor
    audio_np = np.frombuffer(result.stdout, dtype=np.float32).copy()
    return torch.from_numpy(audio_np).unsqueeze(0)


def get_speech_timestamps(
    audio_path: str | Path,
    sample_rate: int = 16000,
    min_silence_duration_ms: int = 300,
) -> list[dict]:
    """使用 silero-vad 检测语音时间段。

    Args:
        audio_path: 音频文件路径
        sample_rate: 采样率
        min_silence_duration_ms: 最小静默时长（毫秒），越大切分越少

    Returns:
        语音时间段列表，每个元素包含 start 和 end（秒）
    """
    # 使用 ffmpeg 加载音频
    waveform = load_audio_with_ffmpeg(audio_path, sample_rate)

    # 使用 silero_vad 包加载模型
    from silero_vad import load_silero_vad, get_speech_timestamps as _get_speech_timestamps
    model = load_silero_vad(onnx=False)

    # 检测语音时间段
    speech_timestamps = _get_speech_timestamps(
        waveform,
        model,
        threshold=0.5,
        sampling_rate=sample_rate,
        min_speech_duration_ms=250,
        min_silence_duration_ms=min_silence_duration_ms,
    )

    # 转换为秒
    result = []
    for ts in speech_timestamps:
        result.append({
            "start": ts["start"] / sample_rate,
            "end": ts["end"] / sample_rate,
        })

    return result


def split_audio_by_vad(
    audio_path: str | Path,
    max_duration: float = 60.0,
    merge_segments: bool = True,
    max_segment_duration: float = 10.0,
    padding_ms: int = 100,
    sample_rate: int = 16000,
) -> list[tuple[Path, float, float]]:
    """使用 VAD 切分长音频。

    Args:
        audio_path: 音频文件路径
        max_duration: 每段最大时长（秒），仅在 merge_segments=True 时生效
        merge_segments: 是否合并短片段，True 用于 ASR 引擎，False 用于字幕生成
        max_segment_duration: 字幕模式下每段最大时长（秒），超过会二次切分
        padding_ms: 前后填充时长（毫秒），防止切分边界漏字
        sample_rate: 采样率

    Returns:
        切分后的音频文件路径和时间戳列表，每个元素为 (path, start, end)
    """
    audio_path = Path(audio_path)

    # 获取音频总时长
    duration = _get_audio_duration(audio_path)

    # 对于字幕模式，使用更短的静默检测
    min_silence = 500 if merge_segments else 300
    speech_timestamps = get_speech_timestamps(audio_path, sample_rate, min_silence)

    if not speech_timestamps:
        # 如果没有检测到语音，按固定时长切分
        if merge_segments:
            return _split_by_fixed_duration(audio_path, max_duration)
        else:
            return [(audio_path, 0.0, duration)]

    # 应用前后填充
    padding_sec = padding_ms / 1000.0
    padded_timestamps = []
    for ts in speech_timestamps:
        padded_start = max(0.0, ts["start"] - padding_sec)
        padded_end = min(duration, ts["end"] + padding_sec)
        padded_timestamps.append({"start": padded_start, "end": padded_end})

    if merge_segments:
        # ASR 模式：合并短片段直到达到 max_duration
        if duration <= max_duration:
            return [(audio_path, 0.0, duration)]
        return _split_at_silence(audio_path, padded_timestamps, max_duration)
    else:
        # 字幕模式：每个 VAD 片段作为一个字幕段，超长片段二次切分
        return _split_subtitles(audio_path, padded_timestamps, max_segment_duration)


def _get_audio_duration(audio_path: Path) -> float:
    """获取音频时长（秒）。"""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def _split_at_silence(
    audio_path: Path,
    speech_timestamps: list[dict],
    max_duration: float,
) -> list[tuple[Path, float, float]]:
    """在语音静默处切分音频，合并短片段直到达到 max_duration。"""
    segments = []
    current_start = 0.0
    current_duration = 0.0

    for ts in speech_timestamps:
        speech_duration = ts["end"] - ts["start"]

        # 如果当前段加上这段语音超过最大时长
        if current_duration + speech_duration > max_duration and current_duration > 0:
            # 在当前语音段之前切分
            segments.append((current_start, ts["start"]))
            current_start = ts["start"]
            current_duration = speech_duration
        else:
            current_duration += speech_duration

    # 添加最后一段
    if current_duration > 0:
        end_time = speech_timestamps[-1]["end"] if speech_timestamps else _get_audio_duration(audio_path)
        segments.append((current_start, end_time))

    # 切分音频
    return _extract_segments(audio_path, segments)


def _split_subtitles(
    audio_path: Path,
    speech_timestamps: list[dict],
    max_segment_duration: float = 10.0,
) -> list[tuple[Path, float, float]]:
    """按 VAD 检测的语音段切分，超长片段进行二次切分。"""
    segments = []
    for ts in speech_timestamps:
        start = ts["start"]
        end = ts["end"]
        duration = end - start

        if duration <= max_segment_duration:
            # 短片段直接使用
            segments.append((start, end))
        else:
            # 长片段按固定时长二次切分
            current = start
            while current < end:
                chunk_end = min(current + max_segment_duration, end)
                segments.append((current, chunk_end))
                current = chunk_end

    return _extract_segments(audio_path, segments)


def _split_by_fixed_duration(audio_path: Path, max_duration: float) -> list[tuple[Path, float, float]]:
    """按固定时长切分音频。"""
    duration = _get_audio_duration(audio_path)
    segments = []
    start = 0.0

    while start < duration:
        end = min(start + max_duration, duration)
        segments.append((start, end))
        start = end

    return _extract_segments(audio_path, segments)


def _extract_segments(audio_path: Path, segments: list[tuple[float, float]]) -> list[tuple[Path, float, float]]:
    """提取音频片段。"""
    result = []

    for i, (start, end) in enumerate(segments):
        output_path = audio_path.parent / f"{audio_path.stem}_part{i:03d}.wav"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(audio_path),
                "-ss", str(start),
                "-to", str(end),
                "-ar", "16000",
                "-ac", "1",
                "-f", "wav",
                str(output_path),
            ],
            capture_output=True,
            check=True,
        )
        result.append((output_path, start, end))

    return result
