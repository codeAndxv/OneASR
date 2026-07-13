"""音视频截取工具类，支持将长音视频按指定时长截取成多个片段。"""

import subprocess
from pathlib import Path


class MediaClipper:
    """音视频截取器，支持按指定时长截取片段。

    使用示例:
        clipper = MediaClipper("/path/to/video.mp4")

        # 截取前2分钟
        clipper.clip(start=0, duration=120, output="/tmp/clip1.mp4")

        # 截取从第5分钟开始的2分钟
        clipper.clip(start=300, duration=120, output="/tmp/clip2.mp4")

        # 自动截取所有2分钟片段
        clips = clipper.auto_clip(clip_duration=120, output_dir="/tmp/clips")
    """

    DEFAULT_CLIP_DURATION = 120  # 默认截取时长：2分钟（秒）

    def __init__(self, input_path: str | Path):
        """初始化截取器。

        Args:
            input_path: 输入音视频文件路径
        """
        self.input_path = Path(input_path)
        if not self.input_path.exists():
            raise FileNotFoundError(f"文件不存在: {self.input_path}")

    def get_duration(self) -> float:
        """获取音视频总时长（秒）。

        Returns:
            音视频时长（秒）
        """
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(self.input_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(result.stdout.strip())

    # 仅音频格式（提取音频，不含视频流）
    AUDIO_ONLY_FORMATS = {"wav", "mp3", "flac", "ogg", "aac", "wma", "opus"}

    def _build_ffmpeg_cmd(
        self, start: float, duration: float, output: Path, target_format: str | None
    ) -> list[str]:
        """构建 ffmpeg 命令。"""
        base = ["ffmpeg", "-y", "-ss", str(start), "-i", str(self.input_path), "-t", str(duration)]

        if target_format is None:
            # 流拷贝模式
            return base + ["-c", "copy", "-avoid_negative_ts", "make_zero", str(output)]

        fmt = target_format.lower().lstrip(".")
        if fmt in self.AUDIO_ONLY_FORMATS:
            # 音频格式：去掉视频流，只保留音频
            return base + ["-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(output)]
        else:
            # 视频格式（mp4, mkv 等）：保留音视频，重新编码
            return base + ["-c:v", "libx264", "-preset", "fast", "-c:a", "aac", str(output)]

    def clip(
        self,
        start: float = 0,
        duration: float | None = None,
        output: str | Path | None = None,
        target_format: str | None = None,
    ) -> Path:
        """截取音视频片段。

        Args:
            start: 开始时间（秒），默认 0
            duration: 截取时长（秒），默认 120 秒（2分钟）
            output: 输出文件路径，默认自动生成
            target_format: 目标格式（如 "wav", "mp3"），指定后先转码再截取。
                          为 None 时使用流拷贝（-c copy），速度快但要求格式兼容。

        Returns:
            输出文件路径
        """
        if duration is None:
            duration = self.DEFAULT_CLIP_DURATION

        if target_format:
            target_suffix = f".{target_format.lstrip('.')}"
        else:
            target_suffix = self.input_path.suffix

        if output is None:
            stem = self.input_path.stem
            output = self.input_path.parent / f"{stem}_clip_{int(start)}{target_suffix}"
        else:
            output = Path(output)

        cmd = self._build_ffmpeg_cmd(start, duration, output, target_format)
        subprocess.run(cmd, capture_output=True, check=True)
        return output

    def auto_clip(
        self,
        clip_duration: float | None = None,
        output_dir: str | Path | None = None,
        target_format: str | None = None,
    ) -> list[Path]:
        """自动将音视频截取成多个片段。

        Args:
            clip_duration: 每个片段的时长（秒），默认 120 秒（2分钟）
            output_dir: 输出目录，默认在输入文件同目录下创建 clips 文件夹
            target_format: 目标格式（如 "wav", "mp3"），指定后转码再截取

        Returns:
            生成的片段文件路径列表
        """
        if clip_duration is None:
            clip_duration = self.DEFAULT_CLIP_DURATION

        total_duration = self.get_duration()

        if output_dir is None:
            output_dir = self.input_path.parent / "clips"
        else:
            output_dir = Path(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)

        suffix = f".{target_format.lstrip('.')}" if target_format else self.input_path.suffix
        clips = []
        start = 0
        index = 0

        while start < total_duration:
            stem = self.input_path.stem
            output_path = output_dir / f"{stem}_part{index:03d}{suffix}"

            self.clip(start=start, duration=clip_duration, output=output_path, target_format=target_format)
            clips.append(output_path)

            start += clip_duration
            index += 1

        return clips

    def clip_to_segments(
        self,
        segment_duration: float | None = None,
    ) -> list[tuple[float, float]]:
        """计算截取的分段信息（不实际截取）。

        Args:
            segment_duration: 每个片段的时长（秒），默认 120 秒（2分钟）

        Returns:
            [(start, end), ...] 时间段列表
        """
        if segment_duration is None:
            segment_duration = self.DEFAULT_CLIP_DURATION

        total_duration = self.get_duration()
        segments = []
        start = 0

        while start < total_duration:
            end = min(start + segment_duration, total_duration)
            segments.append((start, end))
            start += segment_duration

        return segments


def clip_media(
    input_path: str | Path,
    start: float = 0,
    duration: float = 120,
    output: str | Path | None = None,
    target_format: str | None = None,
) -> Path:
    """截取音视频片段的便捷函数。

    Args:
        input_path: 输入文件路径
        start: 开始时间（秒）
        duration: 截取时长（秒）
        output: 输出文件路径
        target_format: 目标格式（如 "wav", "mp3"），指定后转码再截取

    Returns:
        输出文件路径
    """
    clipper = MediaClipper(input_path)
    return clipper.clip(start=start, duration=duration, output=output, target_format=target_format)


def auto_clip_media(
    input_path: str | Path,
    clip_duration: float = 120,
    output_dir: str | Path | None = None,
    target_format: str | None = None,
) -> list[Path]:
    """自动截取所有片段的便捷函数。

    Args:
        input_path: 输入文件路径
        clip_duration: 每个片段的时长（秒）
        output_dir: 输出目录
        target_format: 目标格式（如 "wav", "mp3"），指定后转码再截取

    Returns:
        生成的片段文件路径列表
    """
    clipper = MediaClipper(input_path)
    return clipper.auto_clip(clip_duration=clip_duration, output_dir=output_dir, target_format=target_format)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python clip.py <input_file> [clip_duration] [target_format]")
        print("示例: python clip.py video.mp4 120 wav")
        sys.exit(1)

    input_file = sys.argv[1]
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    target_format = sys.argv[3] if len(sys.argv) > 3 else None

    clipper = MediaClipper(input_file)
    total = clipper.get_duration()
    print(f"文件时长: {total:.1f}秒")

    clips = clipper.auto_clip(clip_duration=duration, target_format=target_format)
    fmt_info = f" (格式: {target_format})" if target_format else ""
    print(f"已截取 {len(clips)} 个片段{fmt_info}:")
    for clip in clips:
        print(f"  - {clip}")
