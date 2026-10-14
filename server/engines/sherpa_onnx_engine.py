"""基于 sherpa-onnx OnlineRecognizer 的实时流式语音识别引擎。

使用 sherpa-onnx 的 OnlineRecognizer 实现高性能流式语音识别。
支持 zipformer2 transducer / conformer 等低延迟流式模型。
"""

import logging
from collections.abc import AsyncIterator
from pathlib import Path

from server.core.config import EngineConfig
from server.engines.base import ASREngine, release_hardware_memory
from server.schemas.audio import Segment
from server.utils.audio_converter import AudioConverter

logger = logging.getLogger(__name__)


class SherpaOnnxStreamSession:
    """sherpa-onnx 流式识别会话，封装 sherpa-onnx OnlineStream。"""

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
        """获取当前部分识别结果的增量文本。"""
        full = self._recognizer.get_result(self._stream).strip()
        if self._final_text and full.startswith(self._final_text):
            current_partial = full[len(self._final_text):].strip()
        else:
            current_partial = full

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
        if self._final_text and full_text.startswith(self._final_text):
            new_text = full_text[len(self._final_text):].strip()
        else:
            new_text = full_text
        self._final_text = full_text
        self._last_partial = ""
        return new_text


class SherpaOnnxEngine(ASREngine):
    """sherpa-onnx 流式识别引擎（基于 sherpa-onnx OnlineRecognizer）。"""

    def __init__(self, config: EngineConfig, lazy_load: bool = False):
        self.config = config
        self.sample_rate: int = int(getattr(config, "sample_rate", 16000))

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

        self._recognizer = None
        self._resolved_paths: tuple[Path, Path, Path, Path] | None = None

        self.validate_config()
        if not lazy_load:
            self.load()

    def validate_config(self) -> None:
        """校验 sherpa-onnx 所需模型文件路径是否完整且存在（零内存开销）。"""
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
                f"[SherpaOnnx] 未配置完整的模型路径，缺失字段: {', '.join(missing_fields)}\n"
                f"sherpa-onnx 引擎不支持在线自动下载，必须在 config.yaml 中配置完整的模型文件路径。\n"
                f"推荐运行一键下载命令:\n"
                f"  uv run python -m cli.model pull {self.config.name}\n"
                f"{'='*70}"
            )
            logger.error(err_msg)
            raise RuntimeError(err_msg)

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
                    f"[SherpaOnnx] 模型文件不存在 ({label}): {p_raw} (绝对路径: {p_resolved})\n"
                    f"请先运行下载命令拉取模型:\n"
                    f"  uv run python -m cli.model pull {self.config.name}\n"
                    f"{'='*70}"
                )
                logger.error(err_msg)
                raise RuntimeError(err_msg)

        self._resolved_paths = (tokens_resolved, encoder_resolved, decoder_resolved, joiner_resolved)

    def load(self) -> None:
        """幂等加载 sherpa-onnx OnlineRecognizer。"""
        if self._recognizer is not None:
            return
        if self._resolved_paths is None:
            self.validate_config()

        import sherpa_onnx

        tokens_resolved, encoder_resolved, decoder_resolved, joiner_resolved = self._resolved_paths
        logger.info(
            "[SherpaOnnx] 正在加载模型: encoder=%s, tokens=%s, decoder=%s, joiner=%s",
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
            logger.info("[SherpaOnnx] 模型加载完成")
        except Exception as e:
            err_msg = f"[SherpaOnnx] 模型初始化失败: {e}"
            logger.error(err_msg, exc_info=True)
            raise RuntimeError(err_msg) from e

    def _ensure_recognizer(self):
        self.load()

    def unload(self) -> None:
        """卸载 sherpa-onnx 识别器并释放内存。"""
        if self._recognizer is not None:
            logger.info("[SherpaOnnx] 正在卸载模型释放内存")
            self._recognizer = None
            release_hardware_memory()

    @property
    def is_loaded(self) -> bool:
        return self._recognizer is not None

    def create_stream_session(self, input_sample_rate: int | None = None) -> SherpaOnnxStreamSession:
        """创建一个新的流式识别会话。"""
        self.load()
        return SherpaOnnxStreamSession(self._recognizer, self.sample_rate, input_sample_rate=input_sample_rate)

    async def transcribe_file(
        self,
        audio_data: bytes,
        language: str | None = None,
        prompt: str | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> tuple[str, list[Segment]]:
        raise NotImplementedError("sherpa-onnx 实时引擎仅支持流式识别，不支持文件转录")

    async def transcribe_file_stream(
        self,
        audio_data: bytes,
        language: str | None = None,
        prompt: str | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> AsyncIterator[Segment]:
        raise NotImplementedError("sherpa-onnx 实时引擎仅支持流式识别，不支持文件转录")
        yield  # pragma: no cover

    async def transcribe_stream(self, audio_chunk: bytes) -> str | None:
        raise NotImplementedError("请使用 create_stream_session() 进行流式识别")

    async def stream_finalize(self) -> str:
        raise NotImplementedError("请使用 create_stream_session() 进行流式识别")


# 别名兼容
XASREngine = SherpaOnnxEngine
XASRStreamingSession = SherpaOnnxStreamSession
