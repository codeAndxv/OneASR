"""X-ASR 流式语音识别引擎（基于 sherpa-onnx）。

使用 sherpa-onnx 的 OnlineRecognizer 实现流式语音识别。
支持 zipformer2 transducer 模型，提供低延迟的实时转录。

配置示例 (config.yaml):
  xasr:
    engine: xasr
    type: local
    model_name: xasr-zh-en
    tokens: models/chunk-160ms-model/tokens.txt
    encoder: models/chunk-160ms-model/encoder-160ms.onnx
    decoder: models/chunk-160ms-model/decoder-160ms.onnx
    joiner: models/chunk-160ms-model/joiner-160ms.onnx
    provider: cpu
    sample_rate: 16000
    feature_dim: 80
    num_threads: 1
    decoding_method: greedy_search
    enable_endpoint_detection: false
"""

import logging
import struct
from collections.abc import AsyncIterator

import numpy as np

from app.core.config import EngineConfig
from app.engines.base import ASREngine
from app.models.schemas import Segment

logger = logging.getLogger(__name__)


class XASRStreamingSession:
    """X-ASR 流式识别会话，封装 sherpa-onnx OnlineStream。"""

    def __init__(self, recognizer, sample_rate: int):
        self._recognizer = recognizer
        self._sample_rate = sample_rate
        self._stream = recognizer.create_stream()
        self._final_text = ""
        self._last_partial = ""

    def accept_audio(self, pcm_bytes: bytes):
        """接收音频数据（float32 PCM 字节），送入识别器。

        客户端发送的是 base64 编码的 float32 PCM，
        解码后为原始字节，转为 numpy float32 数组。
        """
        count = len(pcm_bytes) // 4
        if count == 0:
            return
        samples = np.frombuffer(pcm_bytes, dtype=np.float32, count=count)
        self._stream.accept_waveform(self._sample_rate, samples.tolist())

    def decode(self):
        """运行一轮解码。"""
        self._recognizer.decode_stream(self._stream)

    def get_partial_result(self) -> str:
        """获取当前部分识别结果的增量文本。

        sherpa-onnx 返回累计文本，需要去掉：
        1. 之前已确认的最终文本 (_final_text)
        2. 上次已经发送过的部分文本 (_last_partial)
        只返回真正新增的部分。
        """
        full = self._recognizer.get_result(self._stream).strip()
        # 去掉已确认的最终文本
        if self._final_text and full.startswith(self._final_text):
            current_partial = full[len(self._final_text):].strip()
        else:
            current_partial = full

        # 计算增量：当前部分文本去掉上次已发送的部分
        if self._last_partial and current_partial.startswith(self._last_partial):
            delta = current_partial[len(self._last_partial):]
        else:
            delta = current_partial

        self._last_partial = current_partial
        return delta

    def get_full_text(self) -> str:
        """获取当前完整累计文本。"""
        return self._recognizer.get_result(self._stream).strip()

    def is_endpoint(self) -> bool:
        """检测是否到达语句端点（静音检测）。"""
        return self._recognizer.is_endpoint(self._stream)

    def finalize(self) -> str:
        """结束输入，返回最终识别文本。"""
        self._stream.input_finished()
        self._recognizer.decode_stream(self._stream)
        full_text = self._recognizer.get_result(self._stream).strip()
        # 计算本次新增的文本
        if self._final_text and full_text.startswith(self._final_text):
            new_text = full_text[len(self._final_text):].strip()
        else:
            new_text = full_text
        self._final_text = full_text
        self._last_partial = ""
        return new_text


class XASREngine(ASREngine):
    """X-ASR 流式识别引擎（基于 sherpa-onnx OnlineRecognizer）。"""

    def __init__(self, config: EngineConfig):
        self.config = config
        self.sample_rate: int = int(getattr(config, "sample_rate", 16000))

        # 模型路径
        self._tokens: str = getattr(config, "tokens", "") or ""
        self._encoder: str = getattr(config, "encoder", "") or ""
        self._decoder: str = getattr(config, "decoder", "") or ""
        self._joiner: str = getattr(config, "joiner", "") or ""
        self._provider: str = getattr(config, "provider", "cpu") or "cpu"
        self._num_threads: int = int(getattr(config, "num_threads", 1))
        self._decoding_method: str = getattr(config, "decoding_method", "greedy_search") or "greedy_search"
        self._enable_endpoint_detection: bool = bool(getattr(config, "enable_endpoint_detection", False))

        # 懒加载识别器
        self._recognizer = None

        logger.info(
            "[XASR] 引擎配置: sample_rate=%d, provider=%s, decoding=%s, endpoint=%s",
            self.sample_rate, self._provider, self._decoding_method, self._enable_endpoint_detection,
        )

    def _ensure_recognizer(self):
        """懒加载 sherpa-onnx OnlineRecognizer。"""
        if self._recognizer is not None:
            return

        import sherpa_onnx

        logger.info("[XASR] 正在加载模型: encoder=%s", self._encoder)
        self._recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
            tokens=self._tokens,
            encoder=self._encoder,
            decoder=self._decoder,
            joiner=self._joiner,
            num_threads=self._num_threads,
            sample_rate=self.sample_rate,
            provider=self._provider,
            decoding_method=self._decoding_method,
            enable_endpoint_detection=self._enable_endpoint_detection,
        )
        logger.info("[XASR] 模型加载完成")

    def create_stream_session(self) -> XASRStreamingSession:
        """创建一个新的流式识别会话。"""
        self._ensure_recognizer()
        return XASRStreamingSession(self._recognizer, self.sample_rate)

    # ── ASREngine 接口（文件转录不支持）──

    async def transcribe_file(self, audio_data: bytes) -> tuple[str, list[Segment]]:
        raise NotImplementedError("X-ASR 仅支持实时流式识别，不支持文件转录")

    async def transcribe_stream(self, audio_chunk: bytes) -> str | None:
        raise NotImplementedError("X-ASR 请使用 create_stream_session() 进行流式识别")

    async def stream_finalize(self) -> str:
        raise NotImplementedError("X-ASR 请使用 create_stream_session() 进行流式识别")
