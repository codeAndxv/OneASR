import argparse
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import torch

from app.core.config import EngineConfig
from app.engines.base import ASREngine
from app.models.schemas import Segment
from app.utils.asr_toolkit import ASRToolkit

# 允许加载包含 argparse.Namespace 的模型
torch.serialization.add_safe_globals([argparse.Namespace])


class FireRedEngine(ASREngine):
    """基于 FireRedASR 的 ASR 引擎。"""

    def __init__(self, config: EngineConfig):
        self.config = config
        # FireRedASR 的 from_pretrained 接受 "aed" 或 "llm"
        asr_type = config.model_name.lower()
        if asr_type not in ["aed", "llm"]:
            asr_type = "aed"  # 默认使用 aed

        from fireredasr.models.fireredasr import FireRedAsr
        self.model = FireRedAsr.from_pretrained(asr_type)

    async def transcribe_file(self, audio_data: bytes) -> tuple[str, list[Segment]]:
        """识别音视频文件，返回 (全文文本, 时间轴片段列表)。支持任意长音频。"""
        max_duration = float(self.config.max_duration or 30.0)
        return await ASRToolkit.process_long_audio(
            audio_data=audio_data,
            transcribe_chunk_fn=self._transcribe_chunk,
            max_chunk_duration=max_duration,
        )

    async def transcribe_file_stream(self, audio_data: bytes) -> AsyncIterator[Segment]:
        """流式识别长音频：基于 VAD 切片逐段推理，每识别完一个语音切片即实时 yield。"""
        max_duration = float(self.config.max_duration or 30.0)
        async for seg in ASRToolkit.process_long_audio_stream(
            audio_data=audio_data,
            transcribe_chunk_fn=self._transcribe_chunk,
            max_chunk_duration=max_duration,
        ):
            yield seg

    def _transcribe_chunk(self, chunk: Any, prompt: str = "") -> tuple[str, list[Segment]]:
        """在线程池中执行同步单切片转录。"""
        if hasattr(chunk, "as_temp_wav"):
            with chunk.as_temp_wav() as audio_path:
                return self._do_transcribe(str(audio_path))
        else:
            return self._do_transcribe(str(chunk))

    def _do_transcribe(self, audio_path: str) -> tuple[str, list[Segment]]:
        results = self.model.transcribe(
            batch_uttid=["utt001"],
            batch_wav_path=[audio_path],
        )
        if results:
            text = str(results[0].get("text", "")).strip()
            return text, []
        return "", []

    async def transcribe_stream(self, audio_chunk: bytes) -> str | None:
        raise NotImplementedError("FireRedEngine 暂不支持流式识别")

    async def stream_finalize(self) -> str:
        raise NotImplementedError("FireRedEngine 暂不支持流式识别")
