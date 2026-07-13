import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Optional

from whisperlivekit import AudioProcessor, TranscriptionEngine
from whisperlivekit.config import WhisperLiveKitConfig

from app.core.config import EngineConfig
from app.engines.base import ASREngine
from app.models.schemas import Segment

logger = logging.getLogger(__name__)

# PCM 参数常量
PCM_SAMPLE_RATE = 16000
PCM_BYTES_PER_SAMPLE = 2  # s16le = 2 bytes
PCM_CHUNK_SECONDS = 1  # 每次发送 1 秒


class WhisperLiveKitEngine(ASREngine):
    """基于 WhisperLiveKit 的 ASR 引擎。

    支持文件识别和实时流式识别（通过 WebSocket）。
    流式识别使用 WhisperLiveKit 的 AudioProcessor，提供完整的
    VAD/VAC + ASR + 时间戳对齐 + 说话人分离管道。
    """

    def __init__(self, config: EngineConfig | None = None):
        if config is None:
            from app.core.config import app_config
            config = app_config.get_engine_config("whisperlivekit")

        self.config = config
        self._transcription_engine: Optional[TranscriptionEngine] = None

    @property
    def transcription_engine(self) -> TranscriptionEngine:
        """懒加载 TranscriptionEngine 单例。"""
        if self._transcription_engine is None:
            wlk_config = self._build_wlk_config()
            self._transcription_engine = TranscriptionEngine(config=wlk_config)
            logger.info(
                "WhisperLiveKit TranscriptionEngine 已初始化: backend=%s, policy=%s",
                wlk_config.backend, wlk_config.backend_policy,
            )
        return self._transcription_engine

    def _build_wlk_config(self, language: str | None = None) -> WhisperLiveKitConfig:
        """从 OneASR 的 EngineConfig 构建 WhisperLiveKitConfig。"""
        cfg = self.config
        kwargs = {
            "model_size": cfg.model_name or "base",
            "backend": cfg.backend or "auto",
            "backend_policy": cfg.backend_policy or "simulstreaming",
            "lan": language or cfg.language or "auto",
            "vac": cfg.vac if cfg.vac is not None else True,
            "pcm_input": cfg.pcm_input if cfg.pcm_input is not None else False,
            "diarization": cfg.diarization if cfg.diarization is not None else False,
            "transcription": True,
        }
        if cfg.model_path and cfg.model_path.exists():
            kwargs["model_path"] = str(cfg.model_path)
        if cfg.compute_type:
            kwargs["compute_type"] = cfg.compute_type
        return WhisperLiveKitConfig.from_kwargs(**kwargs)

    def create_audio_processor(
        self,
        language: str | None = None,
        mode: str = "full",
        target_language: str | None = None,
    ) -> AudioProcessor:
        """创建一个新的 AudioProcessor 实例供 WebSocket 连接使用。

        Args:
            language: 可选的语言覆盖（如 "zh"、"en"、"auto"）。
            mode: 识别模式（"full" 或 "diff"）。
            target_language: 翻译目标语言（仅 mode="diff" 时有效）。
        """
        kwargs = {
            "transcription_engine": self.transcription_engine,
            "language": language,
        }
        if mode:
            kwargs["mode"] = mode
        if target_language:
            kwargs["target_language"] = target_language
        return AudioProcessor(**kwargs)

    # ── 文件转录 ────────────────────────────────────────────────

    async def transcribe_file(self, audio_data: bytes) -> tuple[str, list[Segment]]:
        """使用 WhisperLiveKit 的 AudioProcessor 批量处理音频文件。"""
        pcm_data = await asyncio.to_thread(self._convert_to_pcm, audio_data)
        duration_sec = len(pcm_data) / (PCM_SAMPLE_RATE * PCM_BYTES_PER_SAMPLE)

        processor = AudioProcessor(
            transcription_engine=self.transcription_engine,
            pcm_input=True,
        )
        results_gen = await processor.create_tasks()

        final_result = None

        async def collect():
            nonlocal final_result
            async for result in results_gen:
                final_result = result

        collect_task = asyncio.create_task(collect())

        # 分块发送 PCM 数据
        chunk_size = PCM_SAMPLE_RATE * PCM_BYTES_PER_SAMPLE * PCM_CHUNK_SECONDS
        for i in range(0, len(pcm_data), chunk_size):
            await processor.process_audio(pcm_data[i:i + chunk_size])

        # 结束信号
        await processor.process_audio(b"")

        # 动态超时：max(120s, 音频时长 × 2.5)
        timeout_sec = max(120.0, duration_sec * 2.5)
        try:
            await asyncio.wait_for(collect_task, timeout=timeout_sec)
        except asyncio.TimeoutError:
            logger.warning("文件转录超时（%.0fs，音频时长 %.0fs）", timeout_sec, duration_sec)
        finally:
            await processor.cleanup()

        if final_result is None:
            return "", []

        return self._extract_segments(final_result)

    async def transcribe_file_stream(self, audio_data: bytes) -> AsyncIterator[Segment]:
        """流式识别：处理过程中逐句 yield 每个 segment。"""
        pcm_data = await asyncio.to_thread(self._convert_to_pcm, audio_data)

        processor = AudioProcessor(
            transcription_engine=self.transcription_engine,
            pcm_input=True,
        )
        results_gen = await processor.create_tasks()

        async def send_audio():
            chunk_size = PCM_SAMPLE_RATE * PCM_BYTES_PER_SAMPLE * PCM_CHUNK_SECONDS
            for i in range(0, len(pcm_data), chunk_size):
                await processor.process_audio(pcm_data[i:i + chunk_size])
            await processor.process_audio(b"")

        send_task = asyncio.create_task(send_audio())

        try:
            async for result in results_gen:
                d = result.to_dict()
                lines = d.get("lines", [])
                for line in lines:
                    text = line.get("text", "").strip()
                    if not text or line.get("speaker") == -2:
                        continue
                    start = WhisperLiveKitEngine._parse_time(line.get("start", "0:00:00.00"))
                    end = WhisperLiveKitEngine._parse_time(line.get("end", "0:00:00.00"))
                    yield Segment(start=start, end=end, text=text)

    # ── 实时流（WebSocket 使用，此处不可用）────────────────────

    async def transcribe_stream(self, audio_chunk: bytes) -> str | None:
        raise NotImplementedError(
            "WhisperLiveKitEngine 的流式识别请使用 WebSocket 接口 /ws/transcribe/stream"
        )

    async def stream_finalize(self) -> str:
        raise NotImplementedError(
            "WhisperLiveKitEngine 的流式识别请使用 WebSocket 接口 /ws/transcribe/stream"
        )

    async def stream_finalize(self) -> str:
        raise NotImplementedError(
            "WLKEngine 的流式识别请使用 WebSocket 接口 /ws/transcribe/stream"
        )

    # ── 工具方法 ────────────────────────────────────────────────

    @staticmethod
    def _extract_segments(front_data) -> tuple[str, list[Segment]]:
        """从 WhisperLiveKit FrontData 提取文本和 Segment 列表。"""
        d = front_data.to_dict()
        lines = d.get("lines", [])
        segments = []
        text_parts = []
        for line in lines:
            text = line.get("text", "").strip()
            if not text or line.get("speaker") == -2:
                continue
            start = WhisperLiveKitEngine._parse_time(line.get("start", "0:00:00.00"))
            end = WhisperLiveKitEngine._parse_time(line.get("end", "0:00:00.00"))
            segments.append(Segment(start=start, end=end, text=text))
            text_parts.append(text)
        return " ".join(text_parts), segments

    @staticmethod
    def _convert_to_pcm(audio_bytes: bytes) -> bytes:
        """使用 ffmpeg 管道方式将音频转换为 PCM s16le 16kHz mono。"""
        import subprocess

        proc = subprocess.run(
            [
                "ffmpeg", "-i", "pipe:0",
                "-f", "s16le", "-acodec", "pcm_s16le",
                "-ar", str(PCM_SAMPLE_RATE), "-ac", "1",
                "-loglevel", "error",
                "pipe:1",
            ],
            input=audio_bytes,
            capture_output=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg 转换失败: {proc.stderr.decode().strip()}")
        return proc.stdout

    @staticmethod
    def _parse_time(time_str: str) -> float:
        """将 'H:MM:SS.cc' 格式的时间转换为秒数。"""
        parts = time_str.split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return float(parts[0])
