"""基于 Qwen3-ASR 的文件转录引擎。

使用 qwen_asr.Qwen3ASRModel 进行语音识别，支持多语言和时间戳。
"""

import logging
from collections.abc import AsyncIterator
from typing import Any

from server.core.config import EngineConfig
from server.engines.base import ASREngine, release_hardware_memory
from server.schemas.audio import Segment
from server.utils.asr_toolkit import ASRToolkit

logger = logging.getLogger(__name__)


def _apply_transformers_qwen_compat():
    """兼容新版 transformers 与 qwen-asr 0.0.6 的装饰器与注册逻辑。"""
    try:
        import transformers.utils.generic
        from transformers.models.auto import configuration_auto, auto_factory

        _orig_check = getattr(transformers.utils.generic, "check_model_inputs", None)
        if _orig_check:
            def _patched_check(func=None):
                if func is None:
                    return lambda f: _orig_check(f)
                return _orig_check(func)
            transformers.utils.generic.check_model_inputs = _patched_check

        if hasattr(configuration_auto, "CONFIG_MAPPING"):
            _orig_config_reg = configuration_auto.CONFIG_MAPPING.register
            def _patched_config_reg(key, value, exist_ok=True):
                return _orig_config_reg(key, value, exist_ok=True)
            configuration_auto.CONFIG_MAPPING.register = _patched_config_reg

        if hasattr(auto_factory, "_BaseAutoModelClass"):
            _orig_auto_reg = auto_factory._BaseAutoModelClass.register
            @classmethod
            def _patched_auto_reg(cls, config_class, model_class, exist_ok=True):
                return _orig_auto_reg.__func__(cls, config_class, model_class, exist_ok=True)
            auto_factory._BaseAutoModelClass.register = _patched_auto_reg

        if hasattr(auto_factory, "_LazyAutoMapping"):
            _orig_lazy_reg = auto_factory._LazyAutoMapping.register
            def _patched_lazy_reg(self, key, value, exist_ok=True):
                return _orig_lazy_reg(self, key, value, exist_ok=True)
            auto_factory._LazyAutoMapping.register = _patched_lazy_reg
    except Exception as patch_err:
        logger.debug("[Qwen] transformers 兼容补丁应用跳过: %s", patch_err)


class QwenEngine(ASREngine):
    """基于 Qwen3-ASR 的文件转录引擎。"""

    def __init__(self, config: EngineConfig, lazy_load: bool = False):
        self.config = config
        self._model = None
        self._model_name: str = config.model_name or "Qwen/Qwen3-ASR-1.7B"
        self._model_path: str = config.model_path or ""
        self._device: str = getattr(config, "device", "cuda:0") or "cuda:0"
        self._dtype: str = getattr(config, "dtype", "bfloat16") or "bfloat16"
        self._max_new_tokens: int = int(getattr(config, "max_new_tokens", 256) or 256)
        self._max_batch_size: int = int(getattr(config, "max_inference_batch_size", 32) or 32)
        self._forced_aligner_name: str = getattr(config, "forced_aligner_name", "") or ""
        self._forced_aligner_path: str = getattr(config, "forced_aligner_path", "") or ""
        self._language: str = getattr(config, "language", "") or ""

        self._model_to_load: str = ""
        self._aligner_to_load: str = ""

        self.validate_config()
        if not lazy_load:
            self.load()

    def validate_config(self) -> None:
        """校验 Qwen 模型及 ForcedAligner 路径是否存在（零内存开销）。"""
        if self._model_path:
            resolved = self.config.resolve_path(self._model_path)
            if not resolved or not resolved.exists():
                model_hint_name = self._model_name or "Qwen/Qwen3-ASR-1.7B"
                err_msg = (
                    f"\n{'='*70}\n"
                    f"[Qwen] 配置的模型路径不存在: {self._model_path} (绝对路径: {resolved})\n"
                    f"请使用 OneASR 模型下载工具或 Hugging Face / ModelScope CLI 下载对应模型。\n"
                    f"推荐下载命令:\n"
                    f"  0. 使用内置 CLI 一键下载 (推荐):\n"
                    f"     uv run python -m cli.model pull {self.config.name}\n"
                    f"  1. 使用 hf (Hugging Face CLI):\n"
                    f"     hf download {model_hint_name} --local-dir {self._model_path}\n"
                    f"  2. 使用 ModelScope CLI:\n"
                    f"     modelscope download --model {model_hint_name} --local_dir {self._model_path}\n"
                    f"{'='*70}"
                )
                logger.error(err_msg)
                raise RuntimeError(err_msg)
            self._model_to_load = str(resolved)
        elif self._model_name:
            self._model_to_load = self._model_name
        else:
            err_msg = "[Qwen] 未配置 model_path 也未配置 model_name，无法加载模型"
            logger.error(err_msg)
            raise RuntimeError(err_msg)

        if self._forced_aligner_path:
            resolved_fa = self.config.resolve_path(self._forced_aligner_path)
            if not resolved_fa or not resolved_fa.exists():
                fa_hint_name = self._forced_aligner_name or "Qwen/Qwen3-ForcedAligner-0.6B"
                err_msg = (
                    f"\n{'='*70}\n"
                    f"[Qwen] 配置的 ForcedAligner 对齐模型路径不存在: {self._forced_aligner_path} (绝对路径: {resolved_fa})\n"
                    f"请使用 OneASR 模型下载工具或 Hugging Face / ModelScope CLI 下载对应对齐模型。\n"
                    f"推荐下载命令:\n"
                    f"  0. 使用内置 CLI 一键下载 (推荐):\n"
                    f"     uv run python -m cli.model pull {self.config.name} --include-aligner\n"
                    f"  1. 使用 hf (Hugging Face CLI):\n"
                    f"     hf download {fa_hint_name} --local-dir {self._forced_aligner_path}\n"
                    f"  2. 使用 ModelScope CLI:\n"
                    f"     modelscope download --model {fa_hint_name} --local_dir {self._forced_aligner_path}\n"
                    f"{'='*70}"
                )
                logger.error(err_msg)
                raise RuntimeError(err_msg)
            self._aligner_to_load = str(resolved_fa)
        elif self._forced_aligner_name:
            self._aligner_to_load = self._forced_aligner_name

    def load(self) -> None:
        """幂等加载 Qwen3-ASR 模型。"""
        if self._model is not None:
            return
        if not self._model_to_load:
            self.validate_config()

        import torch

        _apply_transformers_qwen_compat()
        from qwen_asr import Qwen3ASRModel

        dtype_map = {
            "bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32,
        }
        dtype = dtype_map.get(self._dtype, torch.bfloat16)

        device = self._device
        if device.startswith("cuda") and not torch.cuda.is_available():
            device = "mps" if torch.backends.mps.is_available() else "cpu"
            if device == "cpu" and dtype == torch.float16:
                dtype = torch.float32
            logger.warning("[Qwen] CUDA 不可用，自动切换至设备: %s (dtype=%s)", device, dtype)

        kwargs = dict(
            dtype=dtype,
            device_map=device,
            max_inference_batch_size=self._max_batch_size,
            max_new_tokens=self._max_new_tokens,
        )

        if self._aligner_to_load:
            kwargs["forced_aligner"] = self._aligner_to_load
            kwargs["forced_aligner_kwargs"] = dict(
                dtype=dtype,
                device_map=device,
            )

        logger.info("[Qwen] 正在加载模型: %s (device=%s, dtype=%s)", self._model_to_load, device, dtype)
        try:
            self._model = Qwen3ASRModel.from_pretrained(self._model_to_load, **kwargs)
            logger.info("[Qwen] 模型加载完成: %s", self._model_to_load)
        except Exception as e:
            err_msg = f"[Qwen] 模型加载失败 ({self._model_to_load}): {e}"
            logger.error(err_msg, exc_info=True)
            raise RuntimeError(err_msg) from e

    def _ensure_model(self):
        self.load()

    def unload(self) -> None:
        """卸载 Qwen3-ASR 模型权重并释放内存。"""
        if self._model is not None:
            logger.info("[Qwen] 正在卸载模型释放内存: %s", self._model_to_load)
            self._model = None
            release_hardware_memory()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @staticmethod
    def normalize_qwen_language(language: str | None) -> str | None:
        """将 ISO-639-1 语言代码或语言名称转换为 Qwen3-ASR 要求的规范英文全称（如 'zh' -> 'Chinese'）。"""
        if not language:
            return None
        raw = str(language).strip().lower()
        if not raw or raw == "auto":
            return None

        iso_to_qwen = {
            "zh": "Chinese",
            "zh-cn": "Chinese",
            "zh-hans": "Chinese",
            "zh-tw": "Chinese",
            "zh-hant": "Chinese",
            "chinese": "Chinese",
            "en": "English",
            "en-us": "English",
            "en-gb": "English",
            "english": "English",
            "yue": "Cantonese",
            "zh-hk": "Cantonese",
            "cantonese": "Cantonese",
            "ar": "Arabic",
            "arabic": "Arabic",
            "de": "German",
            "german": "German",
            "fr": "French",
            "french": "French",
            "es": "Spanish",
            "spanish": "Spanish",
            "pt": "Portuguese",
            "pt-br": "Portuguese",
            "portuguese": "Portuguese",
            "id": "Indonesian",
            "indonesian": "Indonesian",
            "it": "Italian",
            "italian": "Italian",
            "ko": "Korean",
            "korean": "Korean",
            "ru": "Russian",
            "russian": "Russian",
            "th": "Thai",
            "thai": "Thai",
            "vi": "Vietnamese",
            "vietnamese": "Vietnamese",
            "ja": "Japanese",
            "japanese": "Japanese",
            "tr": "Turkish",
            "turkish": "Turkish",
            "hi": "Hindi",
            "hindi": "Hindi",
            "ms": "Malay",
            "malay": "Malay",
            "nl": "Dutch",
            "dutch": "Dutch",
            "sv": "Swedish",
            "swedish": "Swedish",
            "da": "Danish",
            "danish": "Danish",
            "fi": "Finnish",
            "finnish": "Finnish",
            "pl": "Polish",
            "polish": "Polish",
            "cs": "Czech",
            "czech": "Czech",
            "fil": "Filipino",
            "tl": "Filipino",
            "filipino": "Filipino",
            "fa": "Persian",
            "persian": "Persian",
            "el": "Greek",
            "greek": "Greek",
            "ro": "Romanian",
            "romanian": "Romanian",
            "hu": "Hungarian",
            "hungarian": "Hungarian",
            "mk": "Macedonian",
            "macedonian": "Macedonian",
        }
        if raw in iso_to_qwen:
            return iso_to_qwen[raw]
        if "-" in raw and raw.split("-")[0] in iso_to_qwen:
            return iso_to_qwen[raw.split("-")[0]]
        return None

    async def transcribe_file(
        self,
        audio_data: bytes,
        language: str | None = None,
        prompt: str | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> tuple[str, list[Segment]]:
        """识别音频文件，返回 (全文文本, 时间轴片段列表)。支持任意长音频。"""
        self.load()
        eff_lang = self.normalize_qwen_language(language or self._language)
        return await ASRToolkit.process_long_audio(
            audio_data=audio_data,
            transcribe_chunk_fn=lambda chunk, ctx="": self._transcribe_sync(
                chunk, prompt=ctx, language=eff_lang
            ),
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
        eff_lang = self.normalize_qwen_language(language or self._language)
        async for seg in ASRToolkit.process_long_audio_stream(
            audio_data=audio_data,
            transcribe_chunk_fn=lambda chunk, ctx="": self._transcribe_sync(
                chunk, prompt=ctx, language=eff_lang
            ),
            initial_prompt=prompt,
        ):
            yield seg

    def _transcribe_sync(
        self,
        chunk: Any,
        prompt: str = "",
        language: str | None = None,
    ) -> tuple[str, list[Segment]]:
        eff_lang = (
            language
            if language is not None
            else self.normalize_qwen_language(self._language)
        )
        use_timestamps = bool(self._forced_aligner_path or self._forced_aligner_name)

        if hasattr(chunk, "as_temp_wav"):
            with chunk.as_temp_wav() as audio_path:
                return self._do_transcribe(str(audio_path), eff_lang, use_timestamps, prompt)
        else:
            return self._do_transcribe(str(chunk), eff_lang, use_timestamps, prompt)

    def _do_transcribe(
        self,
        audio_path: str,
        language: str | None,
        use_timestamps: bool,
        prompt: str = "",
    ) -> tuple[str, list[Segment]]:
        kwargs: dict[str, Any] = {
            "audio": audio_path,
            "language": language,
            "return_time_stamps": use_timestamps,
        }
        if prompt:
            kwargs["context"] = prompt

        try:
            results = self._model.transcribe(**kwargs)
        except TypeError:
            kwargs.pop("context", None)
            results = self._model.transcribe(**kwargs)

        if not results:
            return "", []

        r = results[0]
        full_text = r.text.strip()

        segments = []
        if use_timestamps and r.time_stamps:
            for ts in r.time_stamps:
                start = getattr(ts, "start_time", None)
                if start is None and isinstance(ts, dict):
                    start = ts.get("start_time", 0.0)
                end = getattr(ts, "end_time", None)
                if end is None and isinstance(ts, dict):
                    end = ts.get("end_time", 0.0)
                text = getattr(ts, "text", None)
                if text is None and isinstance(ts, dict):
                    text = ts.get("text", "")
                segments.append(Segment(
                    start=float(start or 0.0),
                    end=float(end or 0.0),
                    text=str(text or "").strip(),
                ))
        else:
            segments.append(Segment(start=0.0, end=0.0, text=full_text))

        return full_text, segments

    async def transcribe_stream(self, audio_chunk: bytes) -> str | None:
        raise NotImplementedError("QwenEngine 仅支持文件转录，不支持流式识别")

    async def stream_finalize(self) -> str:
        raise NotImplementedError("QwenEngine 仅支持文件转录，不支持流式识别")
