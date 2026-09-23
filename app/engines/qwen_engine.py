"""基于 Qwen3-ASR 的文件转录引擎。

使用 qwen_asr.Qwen3ASRModel 进行语音识别，支持多语言和时间戳。

配置示例 (config.yaml):
  qwen:
    engine: qwen
    type: local
    load:
      model_name: Qwen/Qwen3-ASR-1.7B
      model_path: models/Qwen3-ASR-1.7B
      device: cuda:0
      dtype: bfloat16
      max_new_tokens: 256
      max_inference_batch_size: 32
      forced_aligner_name: Qwen/Qwen3-ForcedAligner-0.6B
      forced_aligner_path: models/Qwen3-ForcedAligner-0.6B
    properties:
      functions:
        - FileASR
"""

import asyncio
import logging
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from app.core.config import EngineConfig
from app.engines.base import ASREngine
from app.models.schemas import Segment
from app.utils.asr_toolkit import ASRToolkit

logger = logging.getLogger(__name__)


def _apply_transformers_qwen_compat():
    """兼容新版 transformers 与 qwen-asr 0.0.6 的装饰器与注册逻辑。"""
    try:
        import transformers.utils.generic
        from transformers.models.auto import configuration_auto, auto_factory

        # 1. 兼容 qwen_asr 中 @check_model_inputs() 的调用形式
        _orig_check = getattr(transformers.utils.generic, "check_model_inputs", None)
        if _orig_check:
            def _patched_check(func=None):
                if func is None:
                    return lambda f: _orig_check(f)
                return _orig_check(func)
            transformers.utils.generic.check_model_inputs = _patched_check

        # 2. 兼容 AutoConfig.register exist_ok
        if hasattr(configuration_auto, "CONFIG_MAPPING"):
            _orig_config_reg = configuration_auto.CONFIG_MAPPING.register
            def _patched_config_reg(key, value, exist_ok=True):
                return _orig_config_reg(key, value, exist_ok=True)
            configuration_auto.CONFIG_MAPPING.register = _patched_config_reg

        # 3. 兼容 AutoModel.register exist_ok
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

    def __init__(self, config: EngineConfig):
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

        # 启动时立即校验路径并加载模型
        self._ensure_model()

    def _ensure_model(self):
        """懒加载 Qwen3-ASR 模型。"""
        if self._model is not None:
            return

        # 1. 先进行路径校验（配置了路径但不存在则立即报错退出）
        model_to_load: str
        if self._model_path:
            resolved = self.config.resolve_path(self._model_path)
            if not resolved or not resolved.exists():
                model_hint_name = self._model_name or "Qwen/Qwen3-ASR-1.7B"
                err_msg = (
                    f"\n{'='*70}\n"
                    f"[Qwen] 配置的模型路径不存在: {self._model_path} (绝对路径: {resolved})\n"
                    f"请使用 Hugging Face CLI 或 ModelScope 下载对应模型。\n"
                    f"推荐下载命令:\n"
                    f"  1. 使用 hf (Hugging Face CLI):\n"
                    f"     hf download {model_hint_name} --local-dir {self._model_path}\n"
                    f"  2. 使用 ModelScope CLI:\n"
                    f"     modelscope download --model {model_hint_name} --local_dir {self._model_path}\n"
                    f"{'='*70}"
                )
                logger.error(err_msg)
                raise RuntimeError(err_msg)
            model_to_load = str(resolved)
        elif self._model_name:
            model_to_load = self._model_name
        else:
            err_msg = "[Qwen] 未配置 model_path 也未配置 model_name，无法加载模型"
            logger.error(err_msg)
            raise RuntimeError(err_msg)

        # 2. 检查 forced_aligner 对齐模型路径
        aligner_to_load: str = ""
        if self._forced_aligner_path:
            resolved_fa = self.config.resolve_path(self._forced_aligner_path)
            if not resolved_fa or not resolved_fa.exists():
                fa_hint_name = self._forced_aligner_name or "Qwen/Qwen3-ForcedAligner-0.6B"
                err_msg = (
                    f"\n{'='*70}\n"
                    f"[Qwen] 配置的 ForcedAligner 对齐模型路径不存在: {self._forced_aligner_path} (绝对路径: {resolved_fa})\n"
                    f"请使用 Hugging Face CLI 或 ModelScope 下载对应对齐模型。\n"
                    f"推荐下载命令:\n"
                    f"  1. 使用 hf (Hugging Face CLI):\n"
                    f"     hf download {fa_hint_name} --local-dir {self._forced_aligner_path}\n"
                    f"  2. 使用 ModelScope CLI:\n"
                    f"     modelscope download --model {fa_hint_name} --local_dir {self._forced_aligner_path}\n"
                    f"{'='*70}"
                )
                logger.error(err_msg)
                raise RuntimeError(err_msg)
            aligner_to_load = str(resolved_fa)
        elif self._forced_aligner_name:
            aligner_to_load = self._forced_aligner_name

        import torch

        # 应用 transformers 兼容补丁以支持 qwen-asr 0.0.6
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

        if aligner_to_load:
            kwargs["forced_aligner"] = aligner_to_load
            kwargs["forced_aligner_kwargs"] = dict(
                dtype=dtype,
                device_map=device,
            )

        logger.info("[Qwen] 正在加载模型: %s (device=%s, dtype=%s)", model_to_load, device, dtype)
        try:
            self._model = Qwen3ASRModel.from_pretrained(model_to_load, **kwargs)
            logger.info("[Qwen] 模型加载完成: %s", model_to_load)
        except Exception as e:
            err_msg = f"[Qwen] 模型加载失败 ({model_to_load}): {e}"
            logger.error(err_msg, exc_info=True)
            raise RuntimeError(err_msg) from e

    async def transcribe_file(self, audio_data: bytes) -> tuple[str, list[Segment]]:
        """识别音频文件，返回 (全文文本, 时间轴片段列表)。支持任意长音频。"""
        self._ensure_model()
        return await ASRToolkit.process_long_audio(
            audio_data=audio_data,
            transcribe_chunk_fn=self._transcribe_sync,
        )

    async def transcribe_file_stream(self, audio_data: bytes) -> AsyncIterator[Segment]:
        """流式识别长音频：基于 VAD 切片逐段推理，每识别完一个语音切片即实时 yield。"""
        self._ensure_model()
        async for seg in ASRToolkit.process_long_audio_stream(
            audio_data=audio_data,
            transcribe_chunk_fn=self._transcribe_sync,
        ):
            yield seg

    def _transcribe_sync(self, chunk: Any, prompt: str = "") -> tuple[str, list[Segment]]:
        """在线程池中执行同步单切片转录，支持 AudioChunk 内存切片及上下文 Prompt。"""
        language = self._language if self._language else None
        use_timestamps = bool(self._forced_aligner_path or self._forced_aligner_name)

        # 处理输入是 AudioChunk 还是普通路径字符串
        if hasattr(chunk, "as_temp_wav"):
            with chunk.as_temp_wav() as audio_path:
                return self._do_transcribe(str(audio_path), language, use_timestamps, prompt)
        else:
            return self._do_transcribe(str(chunk), language, use_timestamps, prompt)

    def _do_transcribe(self, audio_path: str, language: str | None, use_timestamps: bool, prompt: str = "") -> tuple[str, list[Segment]]:
        kwargs: dict[str, Any] = {
            "audio": audio_path,
            "language": language,
            "return_time_stamps": use_timestamps,
        }
        if prompt:
            kwargs["prompt"] = prompt

        try:
            results = self._model.transcribe(**kwargs)
        except TypeError:
            # 如果底层模型接口不支持 prompt 参数，去除后重试
            kwargs.pop("prompt", None)
            results = self._model.transcribe(**kwargs)

        if not results:
            return "", []

        r = results[0]
        full_text = r.text.strip()

        # 解析时间戳
        segments = []
        if use_timestamps and r.time_stamps:
            for ts in r.time_stamps:
                start = getattr(ts, "start_time", None)
                if start is None and isinstance(ts, dict):
                    start = ts.get("start_time", ts.get("start", 0))
                end = getattr(ts, "end_time", None)
                if end is None and isinstance(ts, dict):
                    end = ts.get("end_time", ts.get("end", 0))
                text = getattr(ts, "text", "")
                if not text and isinstance(ts, dict):
                    text = ts.get("text", "")
                segments.append(Segment(
                    start=float(start or 0.0),
                    end=float(end or 0.0),
                    text=str(text or "").strip(),
                ))

        return full_text, segments

    async def transcribe_stream(self, audio_chunk: bytes) -> str | None:
        raise NotImplementedError("QwenEngine 仅支持文件转录")

    async def stream_finalize(self) -> str:
        raise NotImplementedError("QwenEngine 仅支持文件转录")
