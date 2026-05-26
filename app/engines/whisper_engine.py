import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

from faster_whisper import WhisperModel

from app.core.config import EngineConfig
from app.engines.base import ASREngine
from app.models.schemas import Segment


class WhisperEngine(ASREngine):
    """基于 faster-whisper 的 ASR 引擎。"""

    def __init__(self, config: EngineConfig | None = None):
        if config is None:
            from app.core.config import app_config
            config = app_config.get_engine_config("whisper")

        # 检查是否指定了本地模型目录
        if config.model_path and config.model_path.exists():
            model_path = str(config.model_path)
        else:
            model_path = config.model_name  # 使用模型名称，faster-whisper 会自动下载
        self.model = WhisperModel(
            model_path,
            device=config.device,
            compute_type=config.compute_type,
        )

    async def transcribe_file(self, audio_data: bytes) -> tuple[str, list[Segment]]:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = Path(tmp.name)

        try:
            segments_iter, info = self.model.transcribe(str(tmp_path), beam_size=5)
            segments = []
            full_text_parts = []
            for seg in segments_iter:
                segments.append(Segment(start=seg.start, end=seg.end, text=seg.text.strip()))
                full_text_parts.append(seg.text.strip())
            return " ".join(full_text_parts), segments
        finally:
            tmp_path.unlink(missing_ok=True)

    async def transcribe_file_stream(self, audio_data: bytes) -> AsyncIterator[Segment]:
        """流式识别：faster-whisper 的 transcribe 本身返回迭代器，逐句 yield。"""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = Path(tmp.name)

        try:
            segments_iter, info = self.model.transcribe(str(tmp_path), beam_size=5)
            for seg in segments_iter:
                yield Segment(start=seg.start, end=seg.end, text=seg.text.strip())
        finally:
            tmp_path.unlink(missing_ok=True)

    async def transcribe_stream(self, audio_chunk: bytes) -> str | None:
        raise NotImplementedError("WhisperEngine 暂不支持流式识别")

    async def stream_finalize(self) -> str:
        raise NotImplementedError("WhisperEngine 暂不支持流式识别")
