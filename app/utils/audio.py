"""音频转换工具函数。"""

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
