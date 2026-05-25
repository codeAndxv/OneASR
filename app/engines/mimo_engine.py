"""小米 MiMo API 语音识别引擎。"""

import base64

from openai import OpenAI

from app.core.config import EngineConfig
from app.engines.base import ASREngine
from app.models.schemas import Segment


class MiMoEngine(ASREngine):
    """基于小米 MiMo API 的 ASR 引擎。

    文档: https://platform.xiaomimimo.com/docs/zh-CN/usage-guide/multimodal-understanding/audio-understanding
    """

    def __init__(self, config: EngineConfig | None = None):
        if config is None:
            from app.core.config import app_config
            config = app_config.get_engine_config("mimo")

        self.api_key = config.api_key
        base_url = (config.base_url or "https://api.xiaomimimo.com").rstrip("/")
        self._client = OpenAI(api_key=self.api_key, base_url=base_url)

    async def transcribe_file(self, audio_data: bytes) -> tuple[str, list[Segment]]:
        base64_data = base64.b64encode(audio_data).decode("utf-8")
        completion = self._client.chat.completions.create(
            model="mimo-v2.5",
            messages=[
                {"role": "system", "content": "你是一个语音识别工具."},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": f"data:audio/wav;base64,{base64_data}"
                            },
                        },
                        {"type": "text", "text": "只进行语音识别"},
                    ],
                },
            ],
            max_completion_tokens=1024,
        )

        # MiMo 音频识别结果在 reasoning_content 中
        message = completion.choices[0].message
        text = message.reasoning_content or message.content or ""
        segments = [Segment(start=0.0, end=0.0, text=text)]
        return text, segments

    async def transcribe_stream(self, audio_chunk: bytes) -> str | None:
        raise NotImplementedError("MiMoEngine 暂不支持流式识别")

    async def stream_finalize(self) -> str:
        raise NotImplementedError("MiMoEngine 暂不支持流式识别")
