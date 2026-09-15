"""基于 Qwen3-ASR 的文件转录引擎。

使用 qwen_asr.Qwen3ASRModel 进行语音识别，支持多语言和时间戳。

配置示例 (config.yaml):
  qwen:
    engine: qwen
    type: local
    model_name: Qwen/Qwen3-ASR-1.7B
    device: cuda:0
    dtype: bfloat16
    max_new_tokens: 256
    max_inference_batch_size: 32
    forced_aligner: Qwen/Qwen3-ForcedAligner-0.6B
    functions:
      - file
"""

import asyncio
import logging
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

from app.core.config import EngineConfig
from app.engines.base import ASREngine
from app.models.schemas import Segment

logger = logging.getLogger(__name__)


class QwenEngine(ASREngine):
    """基于 Qwen3-ASR 的文件转录引擎。"""

    def __init__(self, config: EngineConfig):
        self.config = config
        self._model = None
        self._model_name: str = config.model_name or "Qwen/Qwen3-ASR-1.7B"
        self._device: str = getattr(config, "device", "cuda:0") or "cuda:0"
        self._dtype: str = getattr(config, "dtype", "bfloat16") or "bfloat16"
        self._max_new_tokens: int = int(getattr(config, "max_new_tokens", 256) or 256)
        self._max_batch_size: int = int(getattr(config, "max_inference_batch_size", 32) or 32)
        self._forced_aligner: str = getattr(config, "forced_aligner", "") or ""
        self._language: str = getattr(config, "language", "") or ""

    def _ensure_model(self):
        """懒加载 Qwen3-ASR 模型。"""
        if self._model is not None:
            return

        import torch
        from qwen_asr import Qwen3ASRModel

        dtype_map = {
            "bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32,
        }
        dtype = dtype_map.get(self._dtype, torch.bfloat16)

        kwargs = dict(
            dtype=dtype,
            device_map=self._device,
            max_inference_batch_size=self._max_batch_size,
            max_new_tokens=self._max_new_tokens,
        )

        # 可选：加载 forced_aligner 以获取时间戳
        if self._forced_aligner:
            kwargs["forced_aligner"] = self._forced_aligner
            kwargs["forced_aligner_kwargs"] = dict(
                dtype=dtype,
                device_map=self._device,
            )

        logger.info("[Qwen] 正在加载模型: %s (device=%s, dtype=%s)", self._model_name, self._device, self._dtype)
        self._model = Qwen3ASRModel.from_pretrained(self._model_name, **kwargs)
        logger.info("[Qwen] 模型加载完成")

    async def transcribe_file(self, audio_data: bytes) -> tuple[str, list[Segment]]:
        """识别音频文件，返回 (全文文本, 时间轴片段列表)。"""
        self._ensure_model()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = Path(tmp.name)

        try:
            result = await asyncio.to_thread(self._transcribe_sync, str(tmp_path))
            return result
        finally:
            tmp_path.unlink(missing_ok=True)

    def _transcribe_sync(self, audio_path: str) -> tuple[str, list[Segment]]:
        """在线程池中执行同步转录。"""
        language = self._language if self._language else None
        use_timestamps = bool(self._forced_aligner)

        results = self._model.transcribe(
            audio=audio_path,
            language=language,
            return_time_stamps=use_timestamps,
        )

        if not results:
            return "", []

        r = results[0]
        full_text = r.text.strip()

        # 解析时间戳
        segments = []
        if use_timestamps and r.time_stamps:
            for ts in r.time_stamps:
                segments.append(Segment(
                    start=float(ts.get("start", 0)),
                    end=float(ts.get("end", 0)),
                    text=ts.get("text", "").strip(),
                ))
        else:
            # 无时间戳时，返回整段
            segments.append(Segment(start=0.0, end=0.0, text=full_text))

        return full_text, segments

    async def transcribe_stream(self, audio_chunk: bytes) -> str | None:
        raise NotImplementedError("QwenEngine 仅支持文件转录")

    async def stream_finalize(self) -> str:
        raise NotImplementedError("QwenEngine 仅支持文件转录")
