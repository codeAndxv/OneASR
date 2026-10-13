"""Audio/video test data generator and local Public Domain fixture loader."""

import io
import math
import struct
import wave
from pathlib import Path

FIXTURES_MEDIA_DIR = Path(__file__).parent.parent / "fixtures" / "media"

EN_SPEECH_SHORT_WAV = "en_speech_15s.wav"
EN_SPEECH_LONG_MP3 = "en_speech_120s.mp3"
EN_VIDEO_MP4 = "en_video_60s.mp4"


def make_pcm_bytes(
    duration_sec: float = 1.0,
    sample_rate: int = 16000,
    frequency: float = 0.0,
    amplitude: float = 0.3,
) -> bytes:
    """生成 16-bit 单声道 PCM 原始字节流（frequency=0.0 时为静音，>0 时为正弦波）。"""
    num_samples = int(duration_sec * sample_rate)
    if frequency <= 0.0:
        return b"\x00\x00" * num_samples

    max_val = int(32767 * min(max(amplitude, 0.0), 1.0))
    samples = [
        int(max_val * math.sin(2.0 * math.pi * frequency * i / sample_rate))
        for i in range(num_samples)
    ]
    return struct.pack(f"<{num_samples}h", *samples)


def make_wav_bytes(
    duration_sec: float = 1.0,
    sample_rate: int = 16000,
    frequency: float = 0.0,
    amplitude: float = 0.3,
) -> bytes:
    """在内存中动态生成合法的单声道 16-bit WAV 字节流（零磁盘 I/O）。"""
    pcm_data = make_pcm_bytes(
        duration_sec=duration_sec,
        sample_rate=sample_rate,
        frequency=frequency,
        amplitude=amplitude,
    )
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


def make_wav_io(
    duration_sec: float = 1.0,
    sample_rate: int = 16000,
    frequency: float = 0.0,
) -> io.BytesIO:
    """返回游标已重置到开头的 WAV BytesIO 对象，可直接用于 FastAPI TestClient 上传。"""
    return io.BytesIO(
        make_wav_bytes(
            duration_sec=duration_sec,
            sample_rate=sample_rate,
            frequency=frequency,
        )
    )


def get_fixture_path(filename: str) -> Path:
    """获取内置 Public Domain 测试媒体文件的完整本地路径。"""
    path = FIXTURES_MEDIA_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"内置测试媒体文件不存在: {path}")
    return path


def load_fixture_media(filename: str) -> bytes:
    """直接从仓库内置 tests/fixtures/media/ 读取无版权测试音频/视频字节流（100% 离线，零网络请求）。"""
    return get_fixture_path(filename).read_bytes()
