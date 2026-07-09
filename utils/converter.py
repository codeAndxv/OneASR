"""音视频格式转换工具类，支持将各种音视频格式转换为 WAV。"""

import subprocess
import tempfile
from pathlib import Path


class AudioConverter:
    """音视频格式转换器，将各种格式转换为 WAV。

    支持的输入格式: mp4, mkv, avi, mov, flv, webm, mp3, flac, aac, ogg, m4a 等
    （任何 ffmpeg 支持的格式）

    使用示例:
        converter = AudioConverter("/path/to/video.mp4")

        # 转换为 WAV（默认 16kHz 单声道）
        wav_path = converter.to_wav()

        # 指定采样率和声道数
        wav_path = converter.to_wav(sample_rate=16000, channels=1)

        # 转换并返回音频数据
        audio_data = converter.to_wav_bytes()
    """

    # ASR 常用参数
    ASR_SAMPLE_RATE = 16000
    ASR_CHANNELS = 1

    def __init__(self, input_path: str | Path):
        """初始化转换器。

        Args:
            input_path: 输入音视频文件路径
        """
        self.input_path = Path(input_path)
        if not self.input_path.exists():
            raise FileNotFoundError(f"文件不存在: {self.input_path}")

    def get_audio_info(self) -> dict:
        """获取音频流信息。

        Returns:
            包含 codec_name, sample_rate, channels, duration 等信息的字典
        """
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_name,sample_rate,channels,duration",
                "-show_entries", "format=duration",
                "-of", "json",
                str(self.input_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        import json
        data = json.loads(result.stdout)

        info = {}
        if "streams" in data and data["streams"]:
            stream = data["streams"][0]
            info["codec_name"] = stream.get("codec_name", "unknown")
            info["sample_rate"] = int(stream.get("sample_rate", 0))
            info["channels"] = int(stream.get("channels", 0))
        if "format" in data:
            info["duration"] = float(data["format"].get("duration", 0))

        return info

    def to_wav(
        self,
        output: str | Path | None = None,
        sample_rate: int = ASR_SAMPLE_RATE,
        channels: int = ASR_CHANNELS,
    ) -> Path:
        """将音视频转换为 WAV 格式。

        Args:
            output: 输出文件路径，默认在输入文件同目录下生成 .wav 文件
            sample_rate: 采样率，默认 16000（ASR 标准）
            channels: 声道数，默认 1（单声道）

        Returns:
            输出 WAV 文件路径
        """
        if output is None:
            output = self.input_path.with_suffix(".wav")
        else:
            output = Path(output)

        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(self.input_path),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", str(sample_rate),
            "-ac", str(channels),
            str(output),
        ]

        subprocess.run(cmd, capture_output=True, check=True)
        return output

    def to_wav_bytes(
        self,
        sample_rate: int = ASR_SAMPLE_RATE,
        channels: int = ASR_CHANNELS,
    ) -> bytes:
        """将音视频转换为 WAV 并返回音频数据。

        Args:
            sample_rate: 采样率，默认 16000
            channels: 声道数，默认 1

        Returns:
            WAV 格式的音频数据
        """
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            self.to_wav(output=tmp.name, sample_rate=sample_rate, channels=channels)
            return Path(tmp.name).read_bytes()

    def to_wav_for_asr(self, output: str | Path | None = None) -> Path:
        """转换为 ASR 标准 WAV（16kHz 单声道）。

        Args:
            output: 输出文件路径

        Returns:
            输出 WAV 文件路径
        """
        return self.to_wav(
            output=output,
            sample_rate=self.ASR_SAMPLE_RATE,
            channels=self.ASR_CHANNELS,
        )


def convert_to_wav(
    input_path: str | Path,
    output: str | Path | None = None,
    sample_rate: int = 16000,
    channels: int = 1,
) -> Path:
    """将音视频转换为 WAV 的便捷函数。

    Args:
        input_path: 输入文件路径
        output: 输出文件路径
        sample_rate: 采样率
        channels: 声道数

    Returns:
        输出 WAV 文件路径
    """
    converter = AudioConverter(input_path)
    return converter.to_wav(output=output, sample_rate=sample_rate, channels=channels)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python converter.py <input_file> [output_file]")
        print("示例: python converter.py video.mp4 output.wav")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    converter = AudioConverter(input_file)
    info = converter.get_audio_info()
    print(f"输入文件: {input_file}")
    print(f"  编码: {info.get('codec_name', 'N/A')}")
    print(f"  采样率: {info.get('sample_rate', 'N/A')} Hz")
    print(f"  声道数: {info.get('channels', 'N/A')}")
    print(f"  时长: {info.get('duration', 0):.1f} 秒")

    wav_path = converter.to_wav(output=output_file)
    print(f"\n转换完成: {wav_path}")
