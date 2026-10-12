"""
FunASR / Paraformer 离线语音识别引擎。

基于阿里开源 FunASR / Paraformer 架构：
1. 非自回归（Non-Autoregressive）推理，彻底杜绝自回归复读与幻听；
2. 原生支持毫秒级时间戳与 CT-Transformer 标点恢复；
3. 支持官方 FunASR Python SDK 或 sherpa-onnx Paraformer 离线引擎；
4. 深度契合中文、中英混合视频长音频转录场景。
"""

import asyncio
import logging
import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

from server.core.config import EngineConfig
from server.engines.base import ASREngine
from server.schemas.audio import Segment, WordTimestamp
from server.utils.subtitle_segmenter import SubtitleSegmenter

logger = logging.getLogger(__name__)


class FunASREngine(ASREngine):
    """阿里 FunASR / Paraformer 语音识别引擎。"""

    def __init__(self, config: EngineConfig):
        self.config = config
        self.segmenter = SubtitleSegmenter()
        self.model_name = config.model_name or "paraformer-zh"
        self.device = config.device or "cpu"

        logger.info(
            "[funasr] 初始化 FunASR 引擎: model=%s, device=%s",
            self.model_name, self.device,
        )
        self._model = None

    def _get_model(self):
        """懒加载模型实例，优先使用 funasr AutoModel，缺失时提示安装。"""
        if self._model is not None:
            return self._model

        try:
            from funasr import AutoModel
        except ImportError as e:
            err_msg = (
                "\n" + "=" * 70 + "\n"
                "[funasr] 未安装 funasr 依赖库，无法使用 FunASR 引擎。\n"
                "推荐安装命令:\n"
                "  pip install funasr modelscope\n"
                + "=" * 70
            )
            logger.error(err_msg)
            raise RuntimeError(err_msg) from e

        model_dir = self.config.model_path or self.model_name
        logger.info("[funasr] 正在加载模型: %s (device=%s)", model_dir, self.device)

        try:
            # 默认加载 paraformer-zh 并搭配标点恢复模型 punc_ct-transformer
            self._model = AutoModel(
                model=model_dir,
                vad_model=self.config.raw_config.get("vad_model", "fsmn-vad"),
                punc_model=self.config.raw_config.get("punc_model", "ct-punc"),
                device=self.device,
                disable_update=True,
            )
            logger.info("[funasr] 模型加载成功: %s", model_dir)
            return self._model
        except Exception as e:
            err_msg = f"[funasr] 模型加载失败 ({model_dir}): {e}"
            logger.error(err_msg, exc_info=True)
            raise RuntimeError(err_msg) from e

    async def transcribe_file(self, audio_data: bytes, **kwargs) -> tuple[str, list[Segment]]:
        """转录音频文件并提取高精度带时间戳片段。"""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = Path(tmp.name)

        loop = asyncio.get_running_loop()

        def _infer():
            model = self._get_model()
            # funasr generate 返回格式: [{'text': '...', 'timestamp': [[start, end], ...], 'sentence_info': [...]}]
            res = model.generate(input=str(tmp_path), batch_size_s=300)
            return res

        try:
            res = await loop.run_in_executor(None, _infer)
            if not res or not isinstance(res, list):
                return "", []

            first_item = res[0]
            full_text = first_item.get("text", "").strip()

            raw_segments: list[Segment] = []
            sentence_info = first_item.get("sentence_info", [])

            if sentence_info:
                for idx, sent in enumerate(sentence_info):
                    text = sent.get("text", "").strip()
                    start_ms = sent.get("start", 0)
                    end_ms = sent.get("end", 0)
                    start_sec = round(start_ms / 1000.0, 3)
                    end_sec = round(end_ms / 1000.0, 3)

                    words: list[WordTimestamp] = []
                    timestamps = sent.get("timestamp", [])
                    clean_chars = [c for c in text if not c.isspace()]
                    if timestamps and len(timestamps) == len(clean_chars):
                        for char, ts in zip(clean_chars, timestamps):
                            if len(ts) >= 2:
                                words.append(
                                    WordTimestamp(
                                        word=char,
                                        start=round(ts[0] / 1000.0, 3),
                                        end=round(ts[1] / 1000.0, 3),
                                    )
                                )

                    raw_segments.append(
                        Segment(
                            id=idx,
                            start=start_sec,
                            end=end_sec,
                            text=text,
                            is_endpoint=True,
                            words=words if words else None,
                        )
                    )
            else:
                # 降级：仅根据总体文本返回单条
                raw_segments.append(
                    Segment(
                        id=0,
                        start=0.0,
                        end=0.0,
                        text=full_text,
                        is_endpoint=True,
                    )
                )

            # 智能规整分段
            optimized = self.segmenter.optimize_segments(raw_segments)
            return full_text, optimized
        finally:
            tmp_path.unlink(missing_ok=True)

    async def transcribe_file_stream(self, audio_data: bytes) -> AsyncIterator[Segment]:
        """将完整转录片段以异步迭代器形式流式吐出。"""
        _, segments = await self.transcribe_file(audio_data)
        for seg in segments:
            yield seg

    async def transcribe_stream(self, audio_chunk: bytes) -> str | None:
        raise NotImplementedError("FunASREngine 建议使用 XASR 进行低延迟实时流式识别")

    async def stream_finalize(self) -> str:
        raise NotImplementedError("FunASREngine 建议使用 XASR 进行低延迟实时流式识别")
