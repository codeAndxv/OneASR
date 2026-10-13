import gc
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from server.schemas.audio import Segment

logger = logging.getLogger(__name__)


def release_hardware_memory():
    """触发 Python GC 并释放 CUDA / Apple MPS 硬件缓存，将空闲内存归还给操作系统。"""
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            torch.mps.empty_cache()
    except Exception:
        pass


class ASREngine(ABC):
    """ASR 引擎统一接口与生命周期协议。所有引擎实现此类。"""

    def validate_config(self) -> None:
        """轻量级校验模型配置与本地文件路径是否存在（不加载权重，耗时 <1ms）。"""
        pass

    def load(self) -> None:
        """将模型权重加载到内存/显存中（幂等操作：若已加载则直接返回）。"""
        pass

    def unload(self) -> None:
        """从内存/显存中卸载模型权重并触发硬件缓存回收（幂等操作）。"""
        for attr in ("model", "_model", "_recognizer"):
            if hasattr(self, attr) and getattr(self, attr) is not None:
                setattr(self, attr, None)
        release_hardware_memory()

    @property
    def is_loaded(self) -> bool:
        """返回底层模型权重当前是否已驻留在内存中。"""
        for attr in ("model", "_model", "_recognizer"):
            if getattr(self, attr, None) is not None:
                return True
        if getattr(self, "_client", None) is not None or getattr(self, "client", None) is not None:
            return True
        return False

    @abstractmethod
    async def transcribe_file(
        self,
        audio_data: bytes,
        language: str | None = None,
        prompt: str | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> tuple[str, list[Segment]]:
        """识别音视频文件，返回 (全文文本, 时间轴片段列表)。"""
        ...

    async def transcribe_file_stream(
        self,
        audio_data: bytes,
        language: str | None = None,
        prompt: str | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> AsyncIterator[Segment]:
        """流式识别音视频文件，每识别完一句即 yield 一个 Segment。

        默认实现调用 transcribe_file 并逐个 yield 段落。
        子类可覆盖以提供更细粒度的流式输出。
        """
        _, segments = await self.transcribe_file(
            audio_data,
            language=language,
            prompt=prompt,
            temperature=temperature,
            **kwargs,
        )
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
