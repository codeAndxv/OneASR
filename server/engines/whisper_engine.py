import asyncio
import logging
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

from faster_whisper import WhisperModel

from server.core.config import EngineConfig, infer_whisper_repo_id
from server.engines.base import ASREngine, release_hardware_memory
from server.schemas.audio import Segment, WordTimestamp
from server.utils.subtitle_segmenter import SubtitleSegmenter

logger = logging.getLogger(__name__)


class WhisperEngine(ASREngine):
    """基于 faster-whisper 的 ASR 引擎（集成抗幻觉、词级时间戳与按需加载/卸载生命周期）。"""

    def __init__(self, config: EngineConfig, lazy_load: bool = False):
        self.config = config
        self.model_name = config.model_name
        self.device = config.device
        self.model: WhisperModel | None = None
        self._model_to_load: str = ""
        self.segmenter = SubtitleSegmenter()

        self.validate_config()
        if not lazy_load:
            self.load()

    def validate_config(self) -> None:
        """校验模型配置与本地路径是否存在（零内存开销）。"""
        if self.config.model_path:
            resolved = self.config.resolve_path(self.config.model_path)
            if not resolved or not resolved.exists():
                repo_id = infer_whisper_repo_id(self.config.model_name)
                err_msg = (
                    f"\n{'='*70}\n"
                    f"[faster-whisper] 配置的模型路径不存在: {self.config.model_path} (绝对路径: {resolved})\n"
                    f"请使用 OneASR 模型下载工具或 Hugging Face / ModelScope CLI 下载对应模型。\n"
                    f"推荐下载命令:\n"
                    f"  0. 使用内置 CLI 一键下载 (推荐):\n"
                    f"     uv run python -m cli.model pull {self.config.name}\n"
                    f"  1. 使用 hf (Hugging Face CLI):\n"
                    f"     hf download {repo_id} --local-dir {self.config.model_path}\n"
                    f"  2. 使用 ModelScope CLI:\n"
                    f"     modelscope download --model {repo_id} --local_dir {self.config.model_path}\n"
                    f"{'='*70}"
                )
                logger.error(err_msg)
                raise RuntimeError(err_msg)
            self._model_to_load = str(resolved)
        elif self.config.model_name:
            self._model_to_load = self.config.model_name
        else:
            err_msg = "[faster-whisper] 未配置 model_path 也未配置 model_name，无法加载模型"
            logger.error(err_msg)
            raise RuntimeError(err_msg)

    def load(self) -> None:
        """幂等加载 faster-whisper 模型权重。"""
        if self.model is not None:
            return
        if not self._model_to_load:
            self.validate_config()

        logger.info(
            "[faster-whisper] 正在加载模型: %s (device=%s, compute_type=%s)",
            self._model_to_load, self.config.device, self.config.compute_type,
        )
        try:
            self.model = WhisperModel(
                self._model_to_load,
                device=self.config.device,
                compute_type=self.config.compute_type,
            )
            logger.info("[faster-whisper] 模型加载成功: %s", self._model_to_load)
        except Exception as e:
            err_msg = f"[faster-whisper] 模型加载失败 ({self._model_to_load}): {e}"
            logger.error(err_msg, exc_info=True)
            raise RuntimeError(err_msg) from e

    def unload(self) -> None:
        """卸载 faster-whisper 模型权重并释放内存。"""
        if self.model is not None:
            logger.info("[faster-whisper] 正在卸载模型释放内存: %s", self._model_to_load)
            self.model = None
            release_hardware_memory()

    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    def _normalize_language(self, language: str | None) -> str | None:
        raw = (language or getattr(self.config, "language", "") or "").strip().lower()
        if not raw or raw == "auto":
            return None
        if raw in ("zh-cn", "zh-hans", "zh-tw", "zh-hant", "chinese"):
            return "zh"
        if raw == "english":
            return "en"
        if raw in ("cantonese", "zh-hk"):
            return "yue"
        if "-" in raw:
            return raw.split("-")[0]
        return raw

    def _build_transcribe_kwargs(
        self,
        language: str | None = None,
        prompt: str | None = None,
        temperature: float | None = None,
        vad_filter: bool = True,
        word_timestamps: bool = True,
    ) -> dict:
        norm_lang = self._normalize_language(language)
        kw = dict(
            language=norm_lang,
            beam_size=5,
            vad_filter=vad_filter,
            vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=200) if vad_filter else None,
            condition_on_previous_text=False,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            no_speech_threshold=0.6,
            word_timestamps=word_timestamps,
        )
        if prompt and prompt.strip():
            kw["initial_prompt"] = prompt.strip()
        if temperature is not None:
            kw["temperature"] = float(temperature)
        return kw

    async def transcribe_file(
        self,
        audio_data: bytes,
        language: str | None = None,
        prompt: str | None = None,
        temperature: float | None = None,
        vad_filter: bool = True,
        word_timestamps: bool = True,
        resegment: bool = True,
        **kwargs,
    ) -> tuple[str, list[Segment]]:
        """文件转录：应用 VAD 静音切片、关闭前文依赖（彻底杜绝幻听滚雪球）、生成词级时间戳并智能规整字幕。"""
        self.load()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = Path(tmp.name)

        transcribe_kwargs = self._build_transcribe_kwargs(
            language=language,
            prompt=prompt,
            temperature=temperature,
            vad_filter=vad_filter,
            word_timestamps=word_timestamps,
        )

        try:
            segments_iter, info = self.model.transcribe(
                str(tmp_path),
                **transcribe_kwargs,
            )

            raw_segments: list[Segment] = []
            full_text_parts: list[str] = []

            for i, seg in enumerate(segments_iter):
                words: list[WordTimestamp] = []
                if hasattr(seg, "words") and seg.words:
                    for w in seg.words:
                        prob = getattr(w, "probability", None)
                        words.append(
                            WordTimestamp(
                                word=w.word,
                                start=round(w.start, 3),
                                end=round(w.end, 3),
                                probability=round(prob, 3) if prob is not None else None,
                            )
                        )

                clean_text = seg.text.strip()
                if clean_text:
                    full_text_parts.append(clean_text)

                avg_prob = getattr(seg, "avg_logprob", None)
                raw_segments.append(
                    Segment(
                        id=i,
                        start=round(seg.start, 3),
                        end=round(seg.end, 3),
                        text=clean_text,
                        is_endpoint=True,
                        words=words if words else None,
                        confidence=round(avg_prob, 3) if avg_prob is not None else None,
                    )
                )

            if resegment and raw_segments:
                final_segments = self.segmenter.optimize_segments(raw_segments)
            else:
                final_segments = raw_segments

            return " ".join(full_text_parts), final_segments
        finally:
            tmp_path.unlink(missing_ok=True)

    async def transcribe_file_stream(
        self,
        audio_data: bytes,
        language: str | None = None,
        prompt: str | None = None,
        temperature: float | None = None,
        vad_filter: bool = True,
        word_timestamps: bool = True,
        **kwargs,
    ) -> AsyncIterator[Segment]:
        """流式识别：在子线程中迭代 faster-whisper，逐句 yield 给 SSE。"""
        self.load()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = Path(tmp.name)

        transcribe_kwargs = self._build_transcribe_kwargs(
            language=language,
            prompt=prompt,
            temperature=temperature,
            vad_filter=vad_filter,
            word_timestamps=word_timestamps,
        )
        queue: asyncio.Queue[Segment | None] = asyncio.Queue()

        def _run():
            try:
                segments_iter, info = self.model.transcribe(
                    str(tmp_path),
                    **transcribe_kwargs,
                )
                for i, seg in enumerate(segments_iter):
                    clean_text = seg.text.strip()
                    if not clean_text:
                        continue

                    words: list[WordTimestamp] = []
                    if hasattr(seg, "words") and seg.words:
                        for w in seg.words:
                            prob = getattr(w, "probability", None)
                            words.append(
                                WordTimestamp(
                                    word=w.word,
                                    start=round(w.start, 3),
                                    end=round(w.end, 3),
                                    probability=round(prob, 3) if prob is not None else None,
                                )
                            )

                    avg_prob = getattr(seg, "avg_logprob", None)
                    asyncio.run_coroutine_threadsafe(
                        queue.put(
                            Segment(
                                id=i,
                                start=round(seg.start, 3),
                                end=round(seg.end, 3),
                                text=clean_text,
                                is_endpoint=True,
                                words=words if words else None,
                                confidence=round(avg_prob, 3) if avg_prob is not None else None,
                            )
                        ),
                        loop,
                    )
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)

        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, _run)

        try:
            while True:
                seg = await queue.get()
                if seg is None:
                    break
                yield seg
        finally:
            tmp_path.unlink(missing_ok=True)

    async def transcribe_stream(self, audio_chunk: bytes) -> str | None:
        raise NotImplementedError("WhisperEngine 暂不支持流式识别")

    async def stream_finalize(self) -> str:
        raise NotImplementedError("WhisperEngine 暂不支持流式识别")
