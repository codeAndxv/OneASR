import tempfile
from pathlib import Path

from faster_whisper import WhisperModel

from app.engines.base import ASREngine
from app.models.schemas import Segment


class WhisperEngine(ASREngine):
    """基于 faster-whisper 的 ASR 引擎。"""

    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8"):
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    async def transcribe_file(self, audio_data: bytes) -> tuple[str, list[Segment]]:
        # 写入临时文件，faster-whisper 需要文件路径
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

    async def transcribe_stream(self, audio_chunk: bytes) -> str | None:
        # 流式识别暂不实现
        raise NotImplementedError("WhisperEngine 暂不支持流式识别")

    async def stream_finalize(self) -> str:
        raise NotImplementedError("WhisperEngine 暂不支持流式识别")
