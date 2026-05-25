"""音频转换工具函数。"""

import base64
import subprocess
from pathlib import Path


def convert_to_wav(input_path: str | Path, sample_rate: int = 16000, channels: int = 1) -> Path:
    """将音视频文件转换为 WAV 格式。

    Args:
        input_path: 输入文件路径
        sample_rate: 采样率，默认 16000
        channels: 声道数，默认 1（单声道）

    Returns:
        转换后的 WAV 文件路径
    """
    input_path = Path(input_path)
    output_path = input_path.with_suffix(".wav")

    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(input_path),
            "-ar", str(sample_rate),
            "-ac", str(channels),
            "-f", "wav",
            str(output_path),
        ],
        capture_output=True,
        check=True,
    )

    return output_path


def audio_to_base64(file_path: str | Path) -> str:
    """将音频文件转换为 Base64 编码字符串。

    Args:
        file_path: 音频文件路径

    Returns:
        Base64 编码的字符串
    """
    file_path = Path(file_path)
    with open(file_path, "rb") as f:
        audio_bytes = f.read()
    return base64.b64encode(audio_bytes).decode("utf-8")
