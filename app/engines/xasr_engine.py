"""X-ASR 流式语音识别引擎（基于 sherpa-onnx）。

使用 sherpa-onnx 的 OnlineRecognizer 实现流式语音识别。
支持 zipformer2 transducer 模型，提供低延迟的实时转录。

配置示例 (config.yaml):
  xasr:
    engine: xasr
    type: local
    load:
      model_name: xasr-zh-en
      tokens_path: models/chunk-160ms-model/tokens.txt
      encoder_path: models/chunk-160ms-model/encoder-160ms.onnx
      decoder_path: models/chunk-160ms-model/decoder-160ms.onnx
      joiner_path: models/chunk-160ms-model/joiner-160ms.onnx
      provider: cpu
      sample_rate: 16000
      feature_dim: 80
      num_threads: 1
      decoding_method: greedy_search
      enable_endpoint_detection: false
    properties:
      functions:
        - RealtimeASR
"""

import logging
from collections.abc import AsyncIterator
from pathlib import Path

import numpy as np

from app.core.config import EngineConfig
from app.engines.base import ASREngine
from app.models.schemas import Segment
from app.utils.audio_converter import AudioConverter

logger = logging.getLogger(__name__)


class XASRStreamingSession:
    """X-ASR 流式识别会话，封装 sherpa-onnx OnlineStream。"""

    def __init__(self, recognizer, sample_rate: int, input_sample_rate: int | None = None):
        self._recognizer = recognizer
        self._sample_rate = sample_rate
        self._input_sample_rate = input_sample_rate or sample_rate
        self._stream = recognizer.create_stream()
        self._final_text = ""
        self._last_partial = ""

    def accept_audio(self, pcm_bytes: bytes, input_sample_rate: int | None = None):
        """接收音频数据，自动进行采样率对齐，并通过 AudioConverter 转为 float32 格式送入识别器。"""
        if not pcm_bytes:
            return

        in_rate = input_sample_rate or self._input_sample_rate or self._sample_rate
        samples = AudioConverter.pcm16_to_float32(pcm_bytes)
        if in_rate != self._sample_rate and len(samples) > 0:
            samples = AudioConverter.resample_float32(samples, in_rate, self._sample_rate)

        if len(samples) > 0:
            self._stream.accept_waveform(self._sample_rate, samples)

    def decode(self):
        """运行解码。必须在 is_ready 为真时才调用 decode_stream，避免底层 C++ 崩溃。"""
        while self._recognizer.is_ready(self._stream):
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

    def reset_endpoint(self):
        """端点重置。"""
        self._recognizer.reset(self._stream)
        self._final_text = ""
        self._last_partial = ""

    def finalize(self) -> str:
        """结束输入，清空剩余帧并返回最终识别文本。"""
        self._stream.input_finished()
        while self._recognizer.is_ready(self._stream):
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
        self._tokens_path: str = getattr(config, "tokens_path", "") or getattr(config, "tokens", "") or ""
        self._encoder_path: str = getattr(config, "encoder_path", "") or getattr(config, "encoder", "") or ""
        self._decoder_path: str = getattr(config, "decoder_path", "") or getattr(config, "decoder", "") or ""
        self._joiner_path: str = getattr(config, "joiner_path", "") or getattr(config, "joiner", "") or ""
        self._provider: str = getattr(config, "provider", "cpu") or "cpu"
        self._num_threads: int = int(getattr(config, "num_threads", 1))
        self._decoding_method: str = getattr(config, "decoding_method", "greedy_search") or "greedy_search"
        self._enable_endpoint_detection: bool = bool(getattr(config, "enable_endpoint_detection", True))
        self._rule1_min_trailing_silence: float = float(getattr(config, "rule1_min_trailing_silence", 2.4))
        self._rule2_min_trailing_silence: float = float(getattr(config, "rule2_min_trailing_silence", 1.2))
        self._rule3_min_utterance_length: float = float(getattr(config, "rule3_min_utterance_length", 20.0))

        # 懒加载识别器
        self._recognizer = None

        logger.info(
            "[XASR] 引擎配置: sample_rate=%d, provider=%s, decoding=%s, endpoint=%s, rule1=%.2fs, rule2=%.2fs, rule3=%.2fs",
            self.sample_rate, self._provider, self._decoding_method, self._enable_endpoint_detection,
            self._rule1_min_trailing_silence, self._rule2_min_trailing_silence, self._rule3_min_utterance_length,
        )

        # 启动时立即校验路径并加载模型
        self._ensure_recognizer()

    def _ensure_recognizer(self):
        """懒加载 sherpa-onnx OnlineRecognizer。"""
        if self._recognizer is not None:
            return

        import sherpa_onnx

        # 1. 检查各路径是否已配置（XASR 无自动下载机制，必须配置路径）
        missing_fields = []
        if not self._tokens_path:
            missing_fields.append("tokens_path")
        if not self._encoder_path:
            missing_fields.append("encoder_path")
        if not self._decoder_path:
            missing_fields.append("decoder_path")
        if not self._joiner_path:
            missing_fields.append("joiner_path")

        if missing_fields:
            err_msg = (
                f"\n{'='*70}\n"
                f"[XASR] 未配置完整的模型路径，缺失字段: {', '.join(missing_fields)}\n"
                f"X-ASR (sherpa-onnx) 引擎不支持在线自动下载，必须在 config.yaml 中配置完整的模型文件路径。\n"
                f"模型获取与配置示例:\n"
                f"  1. 下载预训练模型 (例如 sherpa-onnx zipformer):\n"
                f"     wget https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-zipformer-zh-14M-2023-02-23.tar.bz2\n"
                f"  2. 解压到 models 目录:\n"
                f"     tar xvf sherpa-onnx-streaming-zipformer-zh-14M-2023-02-23.tar.bz2 -C models/\n"
                f"  3. 在 config.yaml 的 xasr.load 中配置:\n"
                f"     tokens_path: models/sherpa-onnx-streaming-zipformer-zh-14M-2023-02-23/tokens.txt\n"
                f"     encoder_path: models/sherpa-onnx-streaming-zipformer-zh-14M-2023-02-23/encoder-epoch-99-avg-1.onnx\n"
                f"     decoder_path: models/sherpa-onnx-streaming-zipformer-zh-14M-2023-02-23/decoder-epoch-99-avg-1.onnx\n"
                f"     joiner_path: models/sherpa-onnx-streaming-zipformer-zh-14M-2023-02-23/joiner-epoch-99-avg-1.onnx\n"
                f"{'='*70}"
            )
            logger.error(err_msg)
            raise RuntimeError(err_msg)

        # 2. 检查各路径文件是否存在
        tokens_resolved = self.config.resolve_path(self._tokens_path)
        encoder_resolved = self.config.resolve_path(self._encoder_path)
        decoder_resolved = self.config.resolve_path(self._decoder_path)
        joiner_resolved = self.config.resolve_path(self._joiner_path)

        for label, p_raw, p_resolved in [
            ("tokens_path", self._tokens_path, tokens_resolved),
            ("encoder_path", self._encoder_path, encoder_resolved),
            ("decoder_path", self._decoder_path, decoder_resolved),
            ("joiner_path", self._joiner_path, joiner_resolved),
        ]:
            if not p_resolved or not p_resolved.exists():
                err_msg = (
                    f"\n{'='*70}\n"
                    f"[XASR] 模型文件不存在 ({label}): {p_raw} (绝对路径: {p_resolved})\n"
                    f"X-ASR (sherpa-onnx) 引擎不支持在线自动下载，请确保模型文件已放置在对应目录。\n"
                    f"{'='*70}"
                )
                logger.error(err_msg)
                raise RuntimeError(err_msg)

        logger.info(
            "[XASR] 正在加载模型: encoder=%s, tokens=%s, decoder=%s, joiner=%s",
            encoder_resolved, tokens_resolved, decoder_resolved, joiner_resolved,
        )
        try:
            self._recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
                tokens=str(tokens_resolved),
                encoder=str(encoder_resolved),
                decoder=str(decoder_resolved),
                joiner=str(joiner_resolved),
                num_threads=self._num_threads,
                sample_rate=self.sample_rate,
                provider=self._provider,
                decoding_method=self._decoding_method,
                enable_endpoint_detection=self._enable_endpoint_detection,
                rule1_min_trailing_silence=self._rule1_min_trailing_silence,
                rule2_min_trailing_silence=self._rule2_min_trailing_silence,
                rule3_min_utterance_length=self._rule3_min_utterance_length,
            )
            logger.info("[XASR] 模型加载完成")
        except Exception as e:
            err_msg = f"[XASR] 模型初始化失败: {e}"
            logger.error(err_msg, exc_info=True)
            raise RuntimeError(err_msg) from e

    def create_stream_session(self, input_sample_rate: int | None = None) -> XASRStreamingSession:
        """创建一个新的流式识别会话。"""
        self._ensure_recognizer()
        return XASRStreamingSession(self._recognizer, self.sample_rate, input_sample_rate=input_sample_rate)

    # ── ASREngine 接口（文件转录不支持）──

    async def transcribe_file(self, audio_data: bytes) -> tuple[str, list[Segment]]:
        raise NotImplementedError("X-ASR 仅支持实时流式识别，不支持文件转录")

    async def transcribe_stream(self, audio_chunk: bytes) -> str | None:
        raise NotImplementedError("X-ASR 请使用 create_stream_session() 进行流式识别")

    async def stream_finalize(self) -> str:
        raise NotImplementedError("X-ASR 请使用 create_stream_session() 进行流式识别")
