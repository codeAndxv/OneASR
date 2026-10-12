import asyncio
import logging
import sys
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

from faster_whisper import WhisperModel

from server.core.config import EngineConfig
from server.engines.base import ASREngine
from server.schemas.audio import Segment, WordTimestamp
from server.utils.subtitle_segmenter import SubtitleSegmenter

logger = logging.getLogger(__name__)


def _infer_whisper_repo_id(model_name: str) -> str:
    """根据 model_name 推导完整的 Hugging Face / ModelScope 仓库 ID。"""
    name = (model_name or "").strip()
    if not name:
        return "Systran/faster-whisper-medium"
    if "/" in name:
        return name
    if name.startswith("faster-whisper-"):
        return f"Systran/{name}"
    return f"Systran/faster-whisper-{name}"


class WhisperEngine(ASREngine):
    """基于 faster-whisper 的 ASR 引擎（集成抗幻觉与词级时间戳优化）。"""

    def __init__(self, config: EngineConfig):
        self.config = config

        model_to_load: str
        if config.model_path:
            resolved = config.resolve_path(config.model_path)
            if not resolved or not resolved.exists():
                repo_id = _infer_whisper_repo_id(config.model_name)
                err_msg = (
                    f"\n{'='*70}\n"
                    f"[faster-whisper] 配置的模型路径不存在: {config.model_path} (绝对路径: {resolved})\n"
                    f"请使用 Hugging Face CLI 或 ModelScope 下载对应模型。\n"
                    f"推荐下载命令:\n"
                    f"  1. 使用 hf (Hugging Face CLI):\n"
                    f"     hf download {repo_id} --local-dir {config.model_path}\n"
                    f"  2. 使用 ModelScope CLI:\n"
                    f"     modelscope download --model {repo_id} --local_dir {config.model_path}\n"
                    f"{'='*70}"
                )
                logger.error(err_msg)
                raise RuntimeError(err_msg)
            model_to_load = str(resolved)
        elif config.model_name:
            model_to_load = config.model_name
        else:
            err_msg = "[faster-whisper] 未配置 model_path 也未配置 model_name，无法加载模型"
            logger.error(err_msg)
            raise RuntimeError(err_msg)

        logger.info(
            "[faster-whisper] 正在加载模型: %s (device=%s, compute_type=%s)",
            model_to_load, config.device, config.compute_type,
        )

        try:
            self.model = WhisperModel(
                model_to_load,
                device=config.device,
                compute_type=config.compute_type,
            )
            logger.info("[faster-whisper] 模型加载成功: %s", model_to_load)
        except Exception as e:
            err_msg = f"[faster-whisper] 模型加载失败 ({model_to_load}): {e}"
            logger.error(err_msg, exc_info=True)
            raise RuntimeError(err_msg) from e

        self.segmenter = SubtitleSegmenter()

    async def transcribe_file(
        self,
        audio_data: bytes,
        language: str | None = None,
        vad_filter: bool = True,
        word_timestamps: bool = True,
        resegment: bool = True,
    ) -> tuple[str, list[Segment]]:
        """文件转录：应用 VAD 静音切片、关闭前文依赖（彻底杜绝幻听滚雪球）、生成词级时间戳并智能规整字幕。"""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = Path(tmp.name)

        try:
            segments_iter, info = self.model.transcribe(
                str(tmp_path),
                language=language,
                beam_size=5,
                vad_filter=vad_filter,
                vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=200) if vad_filter else None,
                condition_on_previous_text=False,  # 关键抗幻听策略：禁止上一句幻觉污染下一句
                compression_ratio_threshold=2.4,  # 检测复读死循环自动重试或跳过
                log_prob_threshold=-1.0,
                no_speech_threshold=0.6,
                word_timestamps=word_timestamps,
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

            # 是否执行智能字幕重断句（根据标点、时长与自然停顿规整）
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
        vad_filter: bool = True,
        word_timestamps: bool = True,
    ) -> AsyncIterator[Segment]:
        """流式识别：在子线程中迭代 faster-whisper，逐句 yield 给 SSE。"""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = Path(tmp.name)

        queue: asyncio.Queue[Segment | None] = asyncio.Queue()

        def _run():
            try:
                segments_iter, info = self.model.transcribe(
                    str(tmp_path),
                    language=language,
                    beam_size=5,
                    vad_filter=vad_filter,
                    vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=200) if vad_filter else None,
                    condition_on_previous_text=False,
                    compression_ratio_threshold=2.4,
                    log_prob_threshold=-1.0,
                    no_speech_threshold=0.6,
                    word_timestamps=word_timestamps,
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
