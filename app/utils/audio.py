"""音频转换工具函数（向后兼容层，底层委托给 AudioConverter）。"""

from pathlib import Path

from app.utils.audio_converter import AudioConverter


def convert_to_wav(input_path: str | Path, sample_rate: int = 16000, channels: int = 1) -> Path:
    """将音视频文件转换为 WAV 格式。"""
    return AudioConverter.convert_file_to_wav(input_path, sample_rate=sample_rate, channels=channels)


def get_wav_duration(audio_data: bytes | str | Path) -> float:
    """快速获取 WAV 音频的时长（秒）。"""
    return AudioConverter.get_audio_duration(audio_data)


def audio_to_base64(file_path: str | Path) -> str:
    """将音频文件转换为 Base64 编码字符串。"""
    file_path = Path(file_path)
    with open(file_path, "rb") as f:
        audio_bytes = f.read()
    return AudioConverter.pcm16_to_base64(audio_bytes)
