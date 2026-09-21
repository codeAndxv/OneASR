import asyncio
import logging
import sys
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

from faster_whisper import WhisperModel

from app.core.config import EngineConfig
from app.engines.base import ASREngine
from app.models.schemas import Segment

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
    """基于 faster-whisper 的 ASR 引擎。"""

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

    async def transcribe_file(self, audio_data: bytes) -> tuple[str, list[Segment]]:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = Path(tmp.name)

        try:
            segments_iter, info = self.model.transcribe(str(tmp_path), beam_size=5)
            segments = []
            full_text_parts = []
            for seg in segments_iter:
                segments.append(Segment(start=seg.start, end=seg.end, text=seg.text.strip(), is_endpoint=True))
                full_text_parts.append(seg.text.strip())
            return " ".join(full_text_parts), segments
        finally:
            tmp_path.unlink(missing_ok=True)

    async def transcribe_file_stream(self, audio_data: bytes) -> AsyncIterator[Segment]:
        """流式识别：在子线程中迭代 faster-whisper，逐句 yield 给 SSE。"""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = Path(tmp.name)

        queue: asyncio.Queue[Segment | None] = asyncio.Queue()

        def _run():
            try:
                segments_iter, info = self.model.transcribe(str(tmp_path), beam_size=5)
                for seg in segments_iter:
                    asyncio.run_coroutine_threadsafe(
                        queue.put(Segment(start=seg.start, end=seg.end, text=seg.text.strip(), is_endpoint=True)),
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
