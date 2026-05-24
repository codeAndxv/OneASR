import argparse
import tempfile
from pathlib import Path

import torch

from app.core.config import EngineConfig
from app.engines.base import ASREngine
from app.models.schemas import Segment
from app.utils.audio import convert_to_wav
from app.utils.vad import split_audio_by_vad

# 允许加载包含 argparse.Namespace 的模型
torch.serialization.add_safe_globals([argparse.Namespace])


class FireRedEngine(ASREngine):
    """基于 FireRedASR 的 ASR 引擎。"""

    def __init__(self, config: EngineConfig):
        self.config = config
        # FireRedASR 的 from_pretrained 接受 "aed" 或 "llm"
        asr_type = config.model_name.lower()
        if asr_type not in ["aed", "llm"]:
            asr_type = "aed"  # 默认使用 aed

        from fireredasr.models.fireredasr import FireRedAsr
        self.model = FireRedAsr.from_pretrained(asr_type)

    async def transcribe_file(self, audio_data: bytes) -> tuple[str, list[Segment]]:
        with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = Path(tmp.name)

        wav_path = None
        audio_parts = []
        try:
            # 转换为 WAV 格式
            wav_path = convert_to_wav(tmp_path)

            # 检查是否需要切分
            max_duration = self.config.max_duration
            if max_duration:
                audio_parts = split_audio_by_vad(wav_path, max_duration)
            else:
                audio_parts = [wav_path]

            # 识别每个片段
            all_text = []
            for part_path in audio_parts:
                results = self.model.transcribe(
                    batch_uttid=["utt001"],
                    batch_wav_path=[str(part_path)],
                )
                if results:
                    all_text.append(results[0]["text"])

            text = " ".join(all_text)
            # FireRedASR 不返回时间轴，整段返回
            segments = [Segment(start=0.0, end=0.0, text=text)] if text else []
            return text, segments
        finally:
            tmp_path.unlink(missing_ok=True)
            if wav_path and wav_path.exists():
                wav_path.unlink(missing_ok=True)
            # 清理切分的临时文件
            for part in audio_parts:
                if part != wav_path and part.exists():
                    part.unlink(missing_ok=True)

    async def transcribe_stream(self, audio_chunk: bytes) -> str | None:
        raise NotImplementedError("FireRedEngine 暂不支持流式识别")

    async def stream_finalize(self) -> str:
        raise NotImplementedError("FireRedEngine 暂不支持流式识别")
