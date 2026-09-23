"""实时语音流模拟工具。

将本地音视频文件转换为音频流，模拟实时音频输入。
支持两种模式：
- PCM 模式：发送原始 PCM 数据（需要服务端 pcm_input=True）
- WAV 模式：发送带 WAV 头的音频块（默认，兼容 FFmpeg 解码）
"""

import asyncio
import io
import logging
import struct
import subprocess
import wave
from pathlib import Path
from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)

from app.utils.audio_converter import AudioConverter

# 音频参数
SAMPLE_RATE = 16000
CHANNELS = 1
BYTES_PER_SAMPLE = 2  # s16le


def convert_to_pcm(input_path: str | Path, sample_rate: int = SAMPLE_RATE) -> bytes:
    """将音视频文件转换为 PCM s16le 原始音频数据。"""
    return AudioConverter.decode_to_pcm16_bytes(input_path, sample_rate=sample_rate)


def pcm_to_wav(pcm_data: bytes, sample_rate: int = SAMPLE_RATE, channels: int = CHANNELS) -> bytes:
    """将 PCM s16le 数据包装为 WAV 格式。"""
    return AudioConverter.pcm16_to_wav_bytes(pcm_data, sample_rate=sample_rate, channels=channels)


def get_audio_duration(pcm_data: bytes, sample_rate: int = SAMPLE_RATE) -> float:
    """计算 PCM 数据的时长（秒）。"""
    return AudioConverter.get_audio_duration(pcm_data, sample_rate=sample_rate, sample_width=BYTES_PER_SAMPLE)


async def stream_pcm_chunks(
    pcm_data: bytes,
    chunk_duration: float = 0.5,
    sample_rate: int = SAMPLE_RATE,
    realtime: bool = True,
) -> AsyncGenerator[bytes, None]:
    """将 PCM 数据按块生成为异步流。

    Args:
        pcm_data: PCM s16le 原始数据
        chunk_duration: 每块的时长（秒），默认 0.5 秒
        sample_rate: 采样率
        realtime: 是否按实时速度发送（True）或尽快发送（False）

    Yields:
        PCM 音频块
    """
    chunk_size = int(sample_rate * BYTES_PER_SAMPLE * chunk_duration)

    for i in range(0, len(pcm_data), chunk_size):
        chunk = pcm_data[i : i + chunk_size]
        yield chunk

        if realtime and i + chunk_size < len(pcm_data):
            await asyncio.sleep(chunk_duration)


async def stream_wav_chunks(
    pcm_data: bytes,
    chunk_duration: float = 0.5,
    sample_rate: int = SAMPLE_RATE,
    realtime: bool = True,
) -> AsyncGenerator[bytes, None]:
    """将 PCM 数据包装为独立的 WAV 块并流式输出。

    每个 chunk 都是一个完整的 WAV 文件，包含正确的 WAV 头。
    这样即使服务端使用 FFmpeg 解码，每个块也能独立解码。

    Args:
        pcm_data: PCM s16le 原始数据
        chunk_duration: 每块的时长（秒），默认 0.5 秒
        sample_rate: 采样率
        realtime: 是否按实时速度发送

    Yields:
        WAV 格式的音频块
    """
    chunk_size = int(sample_rate * BYTES_PER_SAMPLE * chunk_duration)

    for i in range(0, len(pcm_data), chunk_size):
        chunk_pcm = pcm_data[i : i + chunk_size]
        wav_chunk = pcm_to_wav(chunk_pcm, sample_rate)
        yield wav_chunk

        if realtime and i + chunk_size < len(pcm_data):
            await asyncio.sleep(chunk_duration)


async def stream_file_to_pcm(
    file_path: str | Path,
    chunk_duration: float = 0.5,
    realtime: bool = True,
) -> AsyncGenerator[bytes, None]:
    """将音视频文件转换并以实时速度流式输出 PCM 块。

    Args:
        file_path: 音视频文件路径
        chunk_duration: 每块时长（秒），默认 0.5 秒
        realtime: 是否模拟实时速度

    Yields:
        PCM 音频块
    """
    pcm_data = convert_to_pcm(file_path)
    duration = get_audio_duration(pcm_data)
    logger.info("已加载音频文件: %s (%.1f 秒)", file_path, duration)

    async for chunk in stream_pcm_chunks(pcm_data, chunk_duration, realtime=realtime):
        yield chunk


async def stream_file_to_wav(
    file_path: str | Path,
    chunk_duration: float = 0.5,
    realtime: bool = True,
) -> AsyncGenerator[bytes, None]:
    """将音视频文件转换并以实时速度流式输出 WAV 块。

    每个块都是完整的 WAV 文件，兼容 FFmpeg 解码。

    Args:
        file_path: 音视频文件路径
        chunk_duration: 每块时长（秒），默认 0.5 秒
        realtime: 是否模拟实时速度

    Yields:
        WAV 格式的音频块
    """
    pcm_data = convert_to_pcm(file_path)
    duration = get_audio_duration(pcm_data)
    logger.info("已加载音频文件: %s (%.1f 秒)", file_path, duration)

    async for chunk in stream_wav_chunks(pcm_data, chunk_duration, realtime=realtime):
        yield chunk
