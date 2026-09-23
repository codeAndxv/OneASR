"""OneASR 统一音频格式转换与解码工具。

提供全套音频格式转换能力：
1. 流式 PCM 内存转换：PCM16 (S16LE) ↔ Float32 (归一化 [-1.0, 1.0])
2. Base64 音频编解码
3. 内存 WAV 包装与解析
4. 全格式音视频 FFmpeg 内存管道解码 (零磁盘 I/O)
5. 音频时长计算与重采样工具
"""

import base64
import io
import logging
import subprocess
import wave
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# 全局默认参数规范
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHANNELS = 1
PCM16_SAMPLE_WIDTH = 2  # S16LE = 2 字节/采样点
FLOAT32_SAMPLE_WIDTH = 4  # Float32 = 4 字节/采样点


class AudioConverter:
    """音频转换与处理工具类。"""

    # ═══════════════════════════════════════════════════════════════
    # 1. 流式 PCM 内存转换 (Streaming In-Memory PCM)
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def pcm16_to_float32(pcm_bytes: bytes) -> np.ndarray:
        """将 16-bit PCM (S16LE, 2 bytes/sample) 字节流转换为 Float32 NumPy 数组。

        取值范围归一化到 [-1.0, 1.0]。
        具备奇数字节截断对齐与空数据防御能力。
        """
        if not pcm_bytes:
            return np.empty(0, dtype=np.float32)

        # 确保字节数为偶数（16-bit 对齐）
        valid_len = (len(pcm_bytes) // PCM16_SAMPLE_WIDTH) * PCM16_SAMPLE_WIDTH
        if valid_len == 0:
            return np.empty(0, dtype=np.float32)

        if valid_len < len(pcm_bytes):
            pcm_bytes = pcm_bytes[:valid_len]

        samples_i16 = np.frombuffer(pcm_bytes, dtype=np.int16)
        return samples_i16.astype(np.float32) / 32768.0

    @staticmethod
    def float32_to_pcm16(audio_np: np.ndarray) -> bytes:
        """将 Float32 [-1.0, 1.0] NumPy 数组量化并打包为 16-bit PCM (S16LE) 字节流。

        使用 np.clip 限制在 [-1.0, 1.0]，防止爆音溢出。
        """
        if audio_np is None or len(audio_np) == 0:
            return b""

        clamped = np.clip(audio_np, -1.0, 1.0)
        samples_i16 = (clamped * 32767.0).astype(np.int16)
        return samples_i16.tobytes()

    @staticmethod
    def pcm_bytes_to_float32(pcm_bytes: bytes, sample_width: int = 2) -> np.ndarray:
        """通用 PCM 字节转 Float32（支持 16-bit 整数或 32-bit 浮点）。

        Args:
            pcm_bytes: PCM 字节流
            sample_width: 采样字节深度，2 为 Int16，4 为 Float32
        """
        if not pcm_bytes:
            return np.empty(0, dtype=np.float32)

        if sample_width == 2:
            return AudioConverter.pcm16_to_float32(pcm_bytes)
        elif sample_width == 4:
            valid_len = (len(pcm_bytes) // 4) * 4
            if valid_len == 0:
                return np.empty(0, dtype=np.float32)
            return np.frombuffer(pcm_bytes[:valid_len], dtype=np.float32).copy()
        else:
            raise ValueError(f"不支持的 sample_width: {sample_width}，仅支持 2 (int16) 或 4 (float32)")

    # ═══════════════════════════════════════════════════════════════
    # 2. Base64 编码与解码 (Base64 Utilities)
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def base64_to_pcm16(audio_b64: str) -> bytes:
        """将 Base64 编码的音频字符串安全解码为 PCM16 字节。"""
        if not audio_b64:
            return b""
        try:
            return base64.b64decode(audio_b64)
        except Exception as e:
            logger.warning("Base64 音频解码失败: %s", e)
            return b""

    @staticmethod
    def pcm16_to_base64(pcm_bytes: bytes) -> str:
        """将 PCM16 字节流编码为 Base64 字符串。"""
        if not pcm_bytes:
            return ""
        return base64.b64encode(pcm_bytes).decode("ascii")

    # ═══════════════════════════════════════════════════════════════
    # 3. 内存 WAV 包装与解析 (In-Memory WAV Packaging)
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def pcm16_to_wav_bytes(
        pcm_bytes: bytes,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS,
    ) -> bytes:
        """为裸 PCM 16-bit (S16LE) 字节流添加标准 44 字节 WAV 头。"""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(PCM16_SAMPLE_WIDTH)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        return buf.getvalue()

    @staticmethod
    def float32_to_wav_bytes(
        audio_np: np.ndarray,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS,
    ) -> bytes:
        """将 Float32 NumPy 数组量化为标准 16-bit WAV 二进制数据（内存生成）。"""
        pcm16_data = AudioConverter.float32_to_pcm16(audio_np)
        return AudioConverter.pcm16_to_wav_bytes(pcm16_data, sample_rate=sample_rate, channels=channels)

    @staticmethod
    def wav_bytes_to_pcm16(wav_bytes: bytes) -> tuple[bytes, int, int]:
        """解析 WAV 字节数据，提取 (裸 PCM16 字节, 采样率, 声道数)。"""
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            rate = wf.getframerate()
            raw_frames = wf.readframes(wf.getnframes())

        # 如果原 WAV 采样宽度不是 16-bit，在此进行转换
        if sampwidth == 2:
            return raw_frames, rate, channels
        elif sampwidth == 4:
            # Float32 WAV 转 Int16
            float_arr = np.frombuffer(raw_frames, dtype=np.float32)
            pcm16 = AudioConverter.float32_to_pcm16(float_arr)
            return pcm16, rate, channels
        else:
            raise ValueError(f"暂不支持转换采样宽度为 {sampwidth} 字节的 WAV")

    # ═══════════════════════════════════════════════════════════════
    # 4. 全格式音视频 FFmpeg 内存管道解码 (FFmpeg In-Memory Pipeline)
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def decode_to_pcm_float32(
        audio_input: bytes | str | Path,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
    ) -> np.ndarray:
        """通过 FFmpeg 内存管道，将任意音视频格式（MP4/MKV/MP3/M4A/FLAC/AAC 等）直接解码为 Float32 NumPy 数组。

        零磁盘临时文件 I/O，高性能管道流处理。
        """
        ffmpeg_cmd = [
            "ffmpeg",
            "-nostdin",
            "-threads", "0",
            "-loglevel", "error",
        ]

        if isinstance(audio_input, (str, Path)):
            ffmpeg_cmd.extend(["-i", str(audio_input)])
            input_bytes = None
        else:
            ffmpeg_cmd.extend(["-i", "pipe:0"])
            input_bytes = audio_input

        ffmpeg_cmd.extend([
            "-f", "f32le",
            "-acodec", "pcm_f32le",
            "-ac", "1",
            "-ar", str(sample_rate),
            "pipe:1",
        ])

        try:
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE if input_bytes is not None else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout_data, stderr_data = process.communicate(input=input_bytes)
            if process.returncode != 0:
                err_msg = stderr_data.decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"FFmpeg 解码失败 (code {process.returncode}): {err_msg}")

            if not stdout_data:
                return np.empty(0, dtype=np.float32)

            return np.frombuffer(stdout_data, dtype=np.float32).copy()

        except FileNotFoundError:
            raise RuntimeError("系统未检测到 FFmpeg，请确保已安装 FFmpeg 并配置于 PATH 中。")

    @staticmethod
    def decode_to_pcm16_bytes(
        audio_input: bytes | str | Path,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
    ) -> bytes:
        """通过 FFmpeg 将任意音视频格式解码为裸 S16LE (16kHz mono) 字节数据。"""
        float32_np = AudioConverter.decode_to_pcm_float32(audio_input, sample_rate=sample_rate)
        return AudioConverter.float32_to_pcm16(float32_np)

    @staticmethod
    def convert_file_to_wav(
        input_path: str | Path,
        output_path: str | Path | None = None,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS,
    ) -> Path:
        """将磁盘音视频文件转换为标准的 WAV 文件。"""
        input_path = Path(input_path)
        if output_path is None:
            output_path = input_path.with_suffix(".wav")
        else:
            output_path = Path(output_path)

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

    # ═══════════════════════════════════════════════════════════════
    # 5. 音频元数据与时长计算 (Audio Metadata & Duration)
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def get_audio_duration(
        audio_data: bytes | str | Path,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        sample_width: int = PCM16_SAMPLE_WIDTH,
        channels: int = DEFAULT_CHANNELS,
    ) -> float:
        """计算音频时长（秒）。

        优先尝试按标准 WAV 头解析；若不是 WAV，则按裸 PCM 计算。
        """
        # 1. 尝试按 WAV 读取
        try:
            if isinstance(audio_data, (str, Path)):
                with wave.open(str(audio_data), "rb") as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    return round(frames / float(rate), 3) if rate > 0 else 0.0
            else:
                with wave.open(io.BytesIO(audio_data), "rb") as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    return round(frames / float(rate), 3) if rate > 0 else 0.0
        except Exception:
            pass

        # 2. 按裸 PCM 字节计算
        if isinstance(audio_data, bytes):
            bytes_per_sec = sample_rate * sample_width * channels
            if bytes_per_sec > 0:
                return round(len(audio_data) / float(bytes_per_sec), 3)

        return 0.0
