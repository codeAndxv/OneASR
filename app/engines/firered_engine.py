import argparse
import tempfile
from collections.abc import AsyncIterator
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
        audio_segments = []
        try:
            # 转换为 WAV 格式
            wav_path = convert_to_wav(tmp_path)

            # 检查是否需要切分，返回 (path, start, end) 元组
            # 使用 merge_segments=False 按自然停顿切分，生成短字幕
            max_duration = self.config.max_duration
            if max_duration:
                audio_segments = split_audio_by_vad(wav_path, max_duration, merge_segments=False)
            else:
                duration = self._get_duration(wav_path)
                audio_segments = [(wav_path, 0.0, duration)]

            # 识别每个片段
            segments = []
            all_text = []
            for part_path, start, end in audio_segments:
                results = self.model.transcribe(
                    batch_uttid=["utt001"],
                    batch_wav_path=[str(part_path)],
                )
                if results:
                    text = results[0]["text"]
                    all_text.append(text)
                    segments.append(Segment(start=start, end=end, text=text))

            full_text = " ".join(all_text)
            return full_text, segments
        finally:
            tmp_path.unlink(missing_ok=True)
            if wav_path and wav_path.exists():
                wav_path.unlink(missing_ok=True)
            # 清理切分的临时文件
            for part_path, _, _ in audio_segments:
                if part_path != wav_path and part_path.exists():
                    part_path.unlink(missing_ok=True)

    async def transcribe_file_stream(self, audio_data: bytes) -> AsyncIterator[Segment]:
        """流式识别：VAD 切分后逐段识别，每识别完一段即 yield。"""
        with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = Path(tmp.name)

        wav_path = None
        audio_segments = []
        try:
            wav_path = convert_to_wav(tmp_path)

            max_duration = self.config.max_duration
            if max_duration:
                audio_segments = split_audio_by_vad(wav_path, max_duration, merge_segments=False)
            else:
                duration = self._get_duration(wav_path)
                audio_segments = [(wav_path, 0.0, duration)]

            for part_path, start, end in audio_segments:
                results = self.model.transcribe(
                    batch_uttid=["utt001"],
                    batch_wav_path=[str(part_path)],
                )
                if results:
                    text = results[0]["text"]
                    yield Segment(start=start, end=end, text=text)
        finally:
            tmp_path.unlink(missing_ok=True)
            if wav_path and wav_path.exists():
                wav_path.unlink(missing_ok=True)
            for part_path, _, _ in audio_segments:
                if part_path != wav_path and part_path.exists():
                    part_path.unlink(missing_ok=True)

    def _get_duration(self, audio_path: Path) -> float:
        """获取音频时长（秒）。"""
        import subprocess
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
        )
        return float(result.stdout.strip())

    async def transcribe_stream(self, audio_chunk: bytes) -> str | None:
        raise NotImplementedError("FireRedEngine 暂不支持流式识别")

    async def stream_finalize(self) -> str:
        raise NotImplementedError("FireRedEngine 暂不支持流式识别")
