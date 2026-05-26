from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.models.schemas import Segment


class ASREngine(ABC):
    """ASR 引擎统一接口。所有引擎实现此类。"""

    @abstractmethod
    async def transcribe_file(self, audio_data: bytes) -> tuple[str, list[Segment]]:
        """识别音视频文件，返回 (全文文本, 时间轴片段列表)。"""
        ...

    async def transcribe_file_stream(self, audio_data: bytes) -> AsyncIterator[Segment]:
        """流式识别音视频文件，每识别完一句即 yield 一个 Segment。

        默认实现调用 transcribe_file 并逐个 yield 段落。
        子类可覆盖以提供更细粒度的流式输出。
        """
        _, segments = await self.transcribe_file(audio_data)
        for seg in segments:
            yield seg

    @abstractmethod
    async def transcribe_stream(self, audio_chunk: bytes) -> str | None:
        """处理一块流式音频，返回中间结果或 None（未就绪）。"""
        ...

    @abstractmethod
    async def stream_finalize(self) -> str:
        """流式结束时，返回最终识别文本。"""
        ...
