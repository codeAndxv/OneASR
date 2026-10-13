"""
FunASR 离线语音识别引擎（基于 funasr.AutoModel 原生流水线，支持 SenseVoiceSmall / Paraformer 等模型）。
"""

import asyncio
import logging
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

from server.core.config import EngineConfig
from server.engines.base import ASREngine, release_hardware_memory
from server.schemas.audio import Segment, WordTimestamp
from server.utils.subtitle_segmenter import SubtitleSegmenter

logger = logging.getLogger(__name__)


def _clean_funasr_text(text: str) -> str:
    """使用 FunASR 官方内置的 rich_transcription_postprocess 清理 SenseVoice 富文本标签（对普通文本无副作用）。"""
    if not text:
        return ""
    try:
        from funasr.utils.postprocess_utils import rich_transcription_postprocess

        return rich_transcription_postprocess(text).strip()
    except Exception:
        return text.strip()


class FunASREngine(ASREngine):
    """阿里 FunASR 语音识别引擎（支持 SenseVoiceSmall、Paraformer-zh 等模型）。"""

    def __init__(self, config: EngineConfig, lazy_load: bool = True):
        self.config = config
        self.segmenter = SubtitleSegmenter()
        self.model_name: str = config.model_name or "iic/SenseVoiceSmall"
        self.device: str = config.device or "cpu"
        self._model = None

        self._model_to_load: str = ""
        self._vad_to_load: str | None = None
        self._punc_to_load: str | None = None

        self.validate_config()
        if not lazy_load:
            self.load()

    def validate_config(self) -> None:
        """校验本地模型路径是否存在（零内存开销），并解析主模型与 VAD/Punc 子模型加载目标。"""
        # 1. 主模型路径校验
        if self.config.model_path:
            resolved = self.config.resolve_path(self.config.model_path)
            if not resolved or not resolved.exists():
                err_msg = (
                    f"\n{'='*70}\n"
                    f"[funasr] 配置的模型路径不存在: {self.config.model_path} (绝对路径: {resolved})\n"
                    f"请使用 OneASR 模型下载工具一键拉取对应模型:\n"
                    f"  uv run python -m cli.model pull {self.config.name}\n"
                    f"{'='*70}"
                )
                logger.error(err_msg)
                raise RuntimeError(err_msg)
            self._model_to_load = str(resolved)
        else:
            self._model_to_load = self.model_name

        # 2. VAD 子模型路径校验
        vad_path = getattr(self.config, "vad_model_path", "") or ""
        vad_name = getattr(self.config, "vad_model", "") or self.config.raw_config.get("vad_model", "") or ""
        if vad_path:
            resolved_vad = self.config.resolve_path(vad_path)
            if not resolved_vad or not resolved_vad.exists():
                err_msg = (
                    f"\n{'='*70}\n"
                    f"[funasr] 配置的 VAD 模型路径不存在: {vad_path} (绝对路径: {resolved_vad})\n"
                    f"请使用 OneASR 模型下载工具一键拉取对应模型:\n"
                    f"  uv run python -m cli.model pull {self.config.name}\n"
                    f"{'='*70}"
                )
                logger.error(err_msg)
                raise RuntimeError(err_msg)
            self._vad_to_load = str(resolved_vad)
        elif vad_name:
            self._vad_to_load = str(vad_name)
        else:
            self._vad_to_load = None

        # 3. 标点恢复子模型路径校验
        punc_path = getattr(self.config, "punc_model_path", "") or ""
        punc_name = getattr(self.config, "punc_model", "") or self.config.raw_config.get("punc_model", "") or ""
        if punc_path:
            resolved_punc = self.config.resolve_path(punc_path)
            if not resolved_punc or not resolved_punc.exists():
                err_msg = (
                    f"\n{'='*70}\n"
                    f"[funasr] 配置的标点模型路径不存在: {punc_path} (绝对路径: {resolved_punc})\n"
                    f"请使用 OneASR 模型下载工具一键拉取对应模型:\n"
                    f"  uv run python -m cli.model pull {self.config.name}\n"
                    f"{'='*70}"
                )
                logger.error(err_msg)
                raise RuntimeError(err_msg)
            self._punc_to_load = str(resolved_punc)
        elif punc_name:
            self._punc_to_load = str(punc_name)
        else:
            self._punc_to_load = None

    def load(self) -> None:
        self._get_model()

    def unload(self) -> None:
        if self._model is not None:
            logger.info("[funasr] 正在卸载模型释放内存: %s", self._model_to_load or self.model_name)
            self._model = None
            release_hardware_memory()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def _get_model(self):
        """幂等加载模型实例，调用 funasr.AutoModel 原生接口。"""
        if self._model is not None:
            return self._model
        if not self._model_to_load:
            self.validate_config()

        try:
            from funasr import AutoModel
        except ImportError as e:
            err_msg = (
                "\n" + "=" * 70 + "\n"
                "[funasr] 未安装 funasr 依赖库，无法使用 FunASR 引擎。\n"
                "推荐安装命令:\n"
                "  uv pip install funasr modelscope\n"
                + "=" * 70
            )
            logger.error(err_msg)
            raise RuntimeError(err_msg) from e

        logger.info(
            "[funasr] 正在加载模型: model=%s, vad=%s, punc=%s, device=%s",
            self._model_to_load,
            self._vad_to_load,
            self._punc_to_load,
            self.device,
        )

        auto_kwargs: dict = {
            "model": self._model_to_load,
            "device": self.device,
            "disable_update": True,
        }
        if self._vad_to_load:
            auto_kwargs["vad_model"] = self._vad_to_load
            auto_kwargs["vad_kwargs"] = {"max_single_segment_time": 30000}
        if self._punc_to_load:
            auto_kwargs["punc_model"] = self._punc_to_load

        try:
            self._model = AutoModel(**auto_kwargs)
            logger.info("[funasr] 模型加载成功: %s", self._model_to_load)
            return self._model
        except Exception as e:
            err_msg = f"[funasr] 模型加载失败 ({self._model_to_load}): {e}"
            logger.error(err_msg, exc_info=True)
            raise RuntimeError(err_msg) from e

    @staticmethod
    def _normalize_language(language: str | None) -> str:
        """将语言代码归一化为 FunASR (SenseVoice / Paraformer) 支持的格式。"""
        if not language:
            return "auto"
        cleaned = language.strip().lower().replace("_", "-")
        if not cleaned or cleaned in ("auto", "default"):
            return "auto"
        alias_map = {
            "zh": "zh",
            "zh-cn": "zh",
            "zh-hans": "zh",
            "zh-tw": "zh",
            "zh-hant": "zh",
            "zh-hk": "yue",
            "chinese": "zh",
            "cantonese": "yue",
            "yue": "yue",
            "en": "en",
            "en-us": "en",
            "en-gb": "en",
            "english": "en",
            "ja": "ja",
            "jp": "ja",
            "japanese": "ja",
            "ko": "ko",
            "kr": "ko",
            "korean": "ko",
            "nospeech": "nospeech",
        }
        if cleaned in alias_map:
            return alias_map[cleaned]
        primary = cleaned.split("-")[0]
        return alias_map.get(primary, "auto")

    async def transcribe_file(
        self,
        audio_data: bytes,
        language: str | None = None,
        prompt: str | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> tuple[str, list[Segment]]:
        """转录音频文件并提取带时间戳片段。"""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = Path(tmp.name)

        loop = asyncio.get_running_loop()
        raw_lang = language or getattr(self.config, "language", "") or "auto"
        lang = self._normalize_language(raw_lang)
        hotword = (prompt or kwargs.get("hotword") or "").strip()

        def _infer():
            model = self._get_model()
            gen_kwargs: dict = {
                "input": str(tmp_path),
                "cache": {},
                "language": lang,
                "use_itn": True,
                "batch_size_s": 300,
                "merge_vad": True,
                "merge_length_s": 15,
            }
            if hotword:
                gen_kwargs["hotword"] = hotword
            return model.generate(**gen_kwargs)

        try:
            res = await loop.run_in_executor(None, _infer)
            if not res or not isinstance(res, list):
                return "", []

            first_item = res[0]
            full_text = _clean_funasr_text(first_item.get("text", ""))

            raw_segments: list[Segment] = []
            sentence_info = first_item.get("sentence_info")

            if sentence_info and isinstance(sentence_info, list):
                for idx, s in enumerate(sentence_info):
                    s_text = _clean_funasr_text(s.get("text", ""))
                    if not s_text:
                        continue
                    start_ms = float(s.get("start", 0.0))
                    end_ms = float(s.get("end", 0.0))

                    words: list[WordTimestamp] = []
                    ts_list = s.get("timestamp")
                    if ts_list and isinstance(ts_list, list):
                        for w_ts in ts_list:
                            if len(w_ts) >= 2:
                                words.append(
                                    WordTimestamp(
                                        word="",
                                        start=round(w_ts[0] / 1000.0, 3),
                                        end=round(w_ts[1] / 1000.0, 3),
                                    )
                                )

                    raw_segments.append(
                        Segment(
                            id=idx,
                            start=round(start_ms / 1000.0, 3),
                            end=round(end_ms / 1000.0, 3),
                            text=s_text,
                            is_endpoint=True,
                            words=words if words else None,
                        )
                    )
            else:
                ts_list = first_item.get("timestamp")
                start_s = 0.0
                end_s = 0.0
                if ts_list and isinstance(ts_list, list) and len(ts_list) > 0:
                    start_s = round(ts_list[0][0] / 1000.0, 3)
                    end_s = round(ts_list[-1][1] / 1000.0, 3)

                if full_text:
                    raw_segments.append(
                        Segment(
                            id=0,
                            start=start_s,
                            end=end_s,
                            text=full_text,
                            is_endpoint=True,
                        )
                    )

            return full_text, raw_segments
        finally:
            tmp_path.unlink(missing_ok=True)

    async def transcribe_file_stream(
        self,
        audio_data: bytes,
        language: str | None = None,
        prompt: str | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> AsyncIterator[Segment]:
        _, segments = await self.transcribe_file(
            audio_data,
            language=language,
            prompt=prompt,
            temperature=temperature,
            **kwargs,
        )
        for seg in segments:
            yield seg

    async def transcribe_stream(self, audio_chunk: bytes) -> str | None:
        raise NotImplementedError("FunASREngine 为离线文件引擎，流式识别请使用 xasr")

    async def stream_finalize(self) -> str:
        raise NotImplementedError("FunASREngine 为离线文件引擎，流式识别请使用 xasr")

