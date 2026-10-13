"""基于 sherpa-onnx OfflineRecognizer 的 FireRedASR 离线语音识别引擎。"""

import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import numpy as np

from server.core.config import EngineConfig
from server.engines.base import ASREngine, release_hardware_memory
from server.schemas.audio import Segment
from server.utils.asr_toolkit import ASRToolkit
from server.utils.audio_converter import AudioConverter

logger = logging.getLogger(__name__)


def _find_first_existing(directory: Path, candidates: list[str]) -> Path | None:
    for name in candidates:
        p = directory / name
        if p.is_file():
            return p
    return None


class FireRedEngine(ASREngine):
    """基于 sherpa-onnx (OfflineRecognizer.from_fire_red_asr) 的 FireRedASR 引擎。"""

    def __init__(self, config: EngineConfig, lazy_load: bool = False):
        self.config = config
        self._recognizer = None
        self._provider: str = getattr(config, "provider", "") or getattr(config, "device", "cpu") or "cpu"
        if self._provider.startswith("cuda"):
            self._provider = "cuda"
        elif self._provider not in ("cpu", "cuda", "coreml"):
            self._provider = "cpu"
        self._num_threads: int = int(getattr(config, "num_threads", 4) or 4)
        self._decoding_method: str = getattr(config, "decoding_method", "greedy_search") or "greedy_search"
        self._resolved_paths: tuple[Path, Path, Path] | None = None

        self.validate_config()
        if not lazy_load:
            self.load()

    def validate_config(self) -> None:
        """校验本地 FireRedASR ONNX 模型文件 (encoder / decoder / tokens) 是否存在。"""
        encoder_raw = getattr(self.config, "encoder_path", "") or ""
        decoder_raw = getattr(self.config, "decoder_path", "") or ""
        tokens_raw = getattr(self.config, "tokens_path", "") or ""
        model_dir_raw = getattr(self.config, "model_path", "") or ""

        if encoder_raw and decoder_raw and tokens_raw:
            enc_p = self.config.resolve_path(encoder_raw)
            dec_p = self.config.resolve_path(decoder_raw)
            tok_p = self.config.resolve_path(tokens_raw)
            for label, p in [("encoder_path", enc_p), ("decoder_path", dec_p), ("tokens_path", tok_p)]:
                if not p or not p.is_file():
                    raise RuntimeError(
                        f"[FireRed] 模型文件不存在 ({label}): {p}\n"
                        f"请运行: uv run python -m cli.model pull {self.config.name}"
                    )
            self._resolved_paths = (enc_p, dec_p, tok_p)
            return

        if model_dir_raw:
            model_dir = self.config.resolve_path(model_dir_raw)
            if not model_dir or not model_dir.is_dir():
                raise RuntimeError(
                    f"[FireRed] 配置的模型目录不存在: {model_dir_raw} (绝对路径: {model_dir})\n"
                    f"请运行: uv run python -m cli.model pull {self.config.name}"
                )
            enc_p = _find_first_existing(model_dir, ["encoder.int8.onnx", "encoder.onnx"])
            dec_p = _find_first_existing(model_dir, ["decoder.int8.onnx", "decoder.onnx"])
            tok_p = _find_first_existing(model_dir, ["tokens.txt"])
            if not enc_p or not dec_p or not tok_p:
                raise RuntimeError(
                    f"[FireRed] 模型目录缺少 encoder/decoder/tokens.txt 文件: {model_dir}\n"
                    f"请运行: uv run python -m cli.model pull {self.config.name}"
                )
            self._resolved_paths = (enc_p, dec_p, tok_p)

    def load(self) -> None:
        """幂等加载 sherpa-onnx OfflineRecognizer.from_fire_red_asr。"""
        if self._recognizer is not None:
            return
        if self._resolved_paths is None:
            self.validate_config()
        if self._resolved_paths is None:
            raise RuntimeError(
                "[FireRed] 未配置 model_path 或 encoder_path/decoder_path/tokens_path，无法加载模型"
            )

        import sherpa_onnx

        enc_p, dec_p, tok_p = self._resolved_paths
        logger.info(
            "[FireRed] 正在通过 sherpa-onnx 加载模型: encoder=%s, decoder=%s, tokens=%s",
            enc_p,
            dec_p,
            tok_p,
        )
        try:
            self._recognizer = sherpa_onnx.OfflineRecognizer.from_fire_red_asr(
                encoder=str(enc_p),
                decoder=str(dec_p),
                tokens=str(tok_p),
                num_threads=self._num_threads,
                provider=self._provider,
                decoding_method=self._decoding_method,
            )
            logger.info("[FireRed] 模型加载成功")
        except Exception as e:
            err_msg = f"[FireRed] 模型加载失败: {e}"
            logger.error(err_msg, exc_info=True)
            raise RuntimeError(err_msg) from e

    def unload(self) -> None:
        if self._recognizer is not None:
            logger.info("[FireRed] 正在卸载模型释放内存")
            self._recognizer = None
            release_hardware_memory()

    @property
    def is_loaded(self) -> bool:
        return self._recognizer is not None

    async def transcribe_file(
        self,
        audio_data: bytes,
        language: str | None = None,
        prompt: str | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> tuple[str, list[Segment]]:
        """识别音视频文件，返回 (全文文本, 时间轴片段列表)。支持任意长音频。"""
        self.load()
        max_duration = float(self.config.max_duration or 30.0)
        return await ASRToolkit.process_long_audio(
            audio_data=audio_data,
            transcribe_chunk_fn=self._transcribe_chunk,
            max_chunk_duration=max_duration,
            initial_prompt=prompt,
        )

    async def transcribe_file_stream(
        self,
        audio_data: bytes,
        language: str | None = None,
        prompt: str | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> AsyncIterator[Segment]:
        """流式识别长音频：基于 VAD 切片逐段推理，每识别完一个语音切片即实时 yield。"""
        self.load()
        max_duration = float(self.config.max_duration or 30.0)
        async for seg in ASRToolkit.process_long_audio_stream(
            audio_data=audio_data,
            transcribe_chunk_fn=self._transcribe_chunk,
            max_chunk_duration=max_duration,
            initial_prompt=prompt,
        ):
            yield seg

    def _transcribe_chunk(self, chunk: Any, prompt: str = "") -> tuple[str, list[Segment]]:
        if hasattr(chunk, "samples") and hasattr(chunk, "sample_rate"):
            samples = np.asarray(chunk.samples, dtype=np.float32)
            sample_rate = int(chunk.sample_rate)
        else:
            raw_bytes = Path(str(chunk)).read_bytes()
            pcm16 = AudioConverter.decode_to_pcm16_bytes(raw_bytes, sample_rate=16000)
            samples = AudioConverter.pcm16_to_float32(pcm16)
            sample_rate = 16000

        if len(samples) == 0:
            return "", []

        stream = self._recognizer.create_stream()
        stream.accept_waveform(sample_rate, samples)
        self._recognizer.decode_stream(stream)
        text = str(stream.result.text or "").strip()
        return text, []

    async def transcribe_stream(self, audio_chunk: bytes) -> str | None:
        raise NotImplementedError("FireRedEngine 仅支持文件转录，流式识别请使用 xasr")

    async def stream_finalize(self) -> str:
        raise NotImplementedError("FireRedEngine 仅支持文件转录，流式识别请使用 xasr")

