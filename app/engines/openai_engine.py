"""OpenAI Whisper API 语音识别引擎。"""

import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

from openai import OpenAI

from app.core.config import EngineConfig
from app.engines.base import ASREngine
from app.models.schemas import Segment


class OpenAIEngine(ASREngine):
    """基于 OpenAI Whisper API 的 ASR 引擎。"""

    def __init__(self, config: EngineConfig):
        self.client = OpenAI(api_key=config.api_key, base_url=config.base_url)
        self.model = config.model_name or "whisper-1"

    async def transcribe_file(self, audio_data: bytes) -> tuple[str, list[Segment]]:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = Path(tmp.name)

        try:
            with open(tmp_path, "rb") as audio_file:
                response = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    response_format="verbose_json",
                    temperature=0.0,
                )

            # 解析 segments
            segments = []
            if hasattr(response, "segments") and response.segments:
                for seg in response.segments:
                    segments.append(Segment(
                        start=seg["start"],
                        end=seg["end"],
                        text=seg["text"].strip(),
                    ))
            else:
                # 如果没有 segments 信息，整段返回
                text = response.text if hasattr(response, "text") else str(response)
                segments = [Segment(start=0.0, end=0.0, text=text)]

            full_text = response.text if hasattr(response, "text") else str(response)
            return full_text, segments
        finally:
            tmp_path.unlink(missing_ok=True)

    async def transcribe_file_stream(self, audio_data: bytes) -> AsyncIterator[Segment]:
        """流式识别：云端 API 返回完整结果后逐句 yield。"""
        _, segments = await self.transcribe_file(audio_data)
        for seg in segments:
            yield seg

    async def transcribe_stream(self, audio_chunk: bytes) -> str | None:
        raise NotImplementedError("OpenAIEngine 暂不支持流式识别")

    async def stream_finalize(self) -> str:
        raise NotImplementedError("OpenAIEngine 暂不支持流式识别")
