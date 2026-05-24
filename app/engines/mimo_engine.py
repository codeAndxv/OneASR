"""小米 MiMo API 语音识别引擎。"""

import tempfile
from pathlib import Path

import httpx

from app.core.config import EngineConfig
from app.engines.base import ASREngine
from app.models.schemas import Segment


class MiMoEngine(ASREngine):
    """基于小米 MiMo API 的 ASR 引擎。

    文档: https://platform.xiaomimimo.com/docs/zh-CN/usage-guide/multimodal-understanding/audio-understanding
    """

    def __init__(self, config: EngineConfig):
        self.config = config
        self.api_key = config.api_key
        self.base_url = (config.base_url or "https://api.xiaomimimo.com").rstrip("/")
        # 如果 base_url 已经以 /v1 结尾，则不再添加
        if self.base_url.endswith("/v1"):
            self.api_url = f"{self.base_url}/audio/transcriptions"
        else:
            self.api_url = f"{self.base_url}/v1/audio/transcriptions"
        self.model = config.model_name or "mimo-audio"

    async def transcribe_file(self, audio_data: bytes) -> tuple[str, list[Segment]]:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = Path(tmp.name)

        try:
            async with httpx.AsyncClient(timeout=300) as client:
                with open(tmp_path, "rb") as f:
                    response = await client.post(
                        self.api_url,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        files={"file": ("audio.wav", f, "audio/wav")},
                        data={"model": self.model},
                    )
                    response.raise_for_status()
                    result = response.json()

            # 解析响应
            text = result.get("text", "")
            segments_data = result.get("segments", [])

            segments = []
            if segments_data:
                for seg in segments_data:
                    segments.append(Segment(
                        start=seg.get("start", 0.0),
                        end=seg.get("end", 0.0),
                        text=seg.get("text", "").strip(),
                    ))
            else:
                segments = [Segment(start=0.0, end=0.0, text=text)]

            return text, segments
        finally:
            tmp_path.unlink(missing_ok=True)

    async def transcribe_stream(self, audio_chunk: bytes) -> str | None:
        raise NotImplementedError("MiMoEngine 暂不支持流式识别")

    async def stream_finalize(self) -> str:
        raise NotImplementedError("MiMoEngine 暂不支持流式识别")
