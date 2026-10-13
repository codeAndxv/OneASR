"""小米 MiMo API 语音识别引擎。"""

import base64
from collections.abc import AsyncIterator

from openai import OpenAI

from server.core.config import EngineConfig
from server.engines.base import ASREngine
from server.schemas.audio import Segment


class MiMoEngine(ASREngine):
    """基于小米 MiMo API 的 ASR 引擎。

    文档: https://platform.xiaomimimo.com/docs/zh-CN/usage-guide/multimodal-understanding/audio-understanding
    """

    def __init__(self, config: EngineConfig):
        self.api_key = config.api_key
        base_url = (config.base_url or "https://api.xiaomimimo.com").rstrip("/")
        self._client = OpenAI(api_key=self.api_key, base_url=base_url)

    async def transcribe_file(
        self,
        audio_data: bytes,
        language: str | None = None,
        prompt: str | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> tuple[str, list[Segment]]:
        base64_data = base64.b64encode(audio_data).decode("utf-8")
        user_instruction = "只进行语音识别"
        if language and language.strip().lower() not in ("auto", "default"):
            user_instruction += f"，识别语言：{language.strip()}"
        if prompt and prompt.strip():
            user_instruction += f"，上下文提示词：{prompt.strip()}"

        create_kwargs: dict = {
            "model": "mimo-v2.5",
            "messages": [
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
                        {"type": "text", "text": user_instruction},
                    ],
                },
            ],
            "max_completion_tokens": 1024,
        }
        if temperature is not None:
            create_kwargs["temperature"] = float(temperature)

        completion = self._client.chat.completions.create(**create_kwargs)

        # MiMo 音频识别结果在 reasoning_content 中
        message = completion.choices[0].message
        text = message.reasoning_content or message.content or ""
        segments = [Segment(start=0.0, end=0.0, text=text)]
        return text, segments

    async def transcribe_file_stream(
        self,
        audio_data: bytes,
        language: str | None = None,
        prompt: str | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> AsyncIterator[Segment]:
        """流式识别：云端 API 返回完整结果后逐句 yield。"""
        _, segments = await self.transcribe_file(
            audio_data,
            language=language,
            prompt=prompt,
            temperature=temperature,
            **kwargs,
        )
        for seg in segments:
            yield seg

    async def transcribe_stream(self, audio_chunk: bytes) -> str | None:
        raise NotImplementedError("MiMoEngine 暂不支持流式识别")

    async def stream_finalize(self) -> str:
        raise NotImplementedError("MiMoEngine 暂不支持流式识别")
