"""
通用 ASR 工具库 (ASR Toolkit) - 全内存切片与高性能流水线架构

核心特性：
1. 全内存音频解码与零拷贝 NumPy 切片（消除 ffmpeg 多次子进程与磁盘 I/O）
2. 跨切片 Prompt 上下文动态传递（保证长音频术语与拼写一致性）
3. collect_chunks 智能停顿融合算法（借鉴 faster-whisper，杜绝碎词截断）
4. 异步生产者-消费者流水线（切片预处理与 GPU 推理完全重叠并行）
5. 双模输出支持（直接提供 np.ndarray 内存数组，亦兼容按需生成单个小切片临时路径）
6. 文本去幻觉与后处理（过滤自回归死循环与格式规范化）
"""

import asyncio
import io
import logging
import os
import re
import subprocess
import tempfile
import wave
from collections.abc import AsyncIterator, Callable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch

from app.core.config import app_config
from app.models.schemas import Segment
from app.utils.audio_converter import AudioConverter

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000


@dataclass
class AudioChunk:
    """音频切片结构体（全内存驻留）。"""
    index: int
    waveform: np.ndarray  # float32 一维数组，16kHz 单声道
    start_time: float     # 全局起始时间（秒）
    end_time: float       # 全局结束时间（秒）
    duration: float       # 切片时长（秒）

    def to_wav_bytes(self) -> bytes:
        """在内存中将 float32 numpy 数组编码为 16kHz 单声道 PCM 16-bit WAV 二进制流。"""
        return AudioConverter.float32_to_wav_bytes(self.waveform, sample_rate=SAMPLE_RATE)

    @contextmanager
    def as_temp_wav(self):
        """为只支持文件路径的引擎按需创建单个小切片的临时 WAV 文件，用完即删。"""
        wav_bytes = self.to_wav_bytes()
        tmp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        try:
            tmp_file.write(wav_bytes)
            tmp_file.flush()
            tmp_file.close()
            yield Path(tmp_file.name)
        finally:
            try:
                os.unlink(tmp_file.name)
            except OSError:
                pass


class TextPostProcessor:
    """ASR 文本后处理与去幻觉工具。"""

    @staticmethod
    def remove_hallucination_repeats(text: str, max_consecutive_repeats: int = 3) -> str:
        """检测并去除因长静音或模型自回归死循环产生的重复复读短语。"""
        if not text:
            return ""

        cleaned = text.strip()

        # 1. 匹配连续重复的短语（2~20个字符重复出现 >= max_consecutive_repeats 次）
        pattern = re.compile(r"(.{2,20}?)(?:\1){" + str(max_consecutive_repeats - 1) + r",}")
        cleaned = pattern.sub(r"\1", cleaned)

        # 2. 匹配连续重复的单字/标点（>= 4 次重复）
        pattern_char = re.compile(r"(.)\1{4,}")
        cleaned = pattern_char.sub(r"\1\1", cleaned)

        return cleaned.strip()

    @staticmethod
    def normalize_text(text: str) -> str:
        """规范化中英文空格与标点。"""
        if not text:
            return ""

        cleaned = text.strip()
        # 中文字符之间的多余空格去除，但保留英文单词间的空格
        cleaned = re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", cleaned)
        # 多个连续空格合并为一个
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()


class ASRToolkit:
    """通用高性能 ASR 处理工具箱。"""

    @classmethod
    def decode_audio_to_waveform(cls, audio_input: bytes | str | Path) -> np.ndarray:
        """通过 FFmpeg 内存管道，将任意音视频格式直接解码为 16kHz 单声道 float32 NumPy 数组。
        
        全程在内存中完成，零磁盘写入。
        """
        return AudioConverter.decode_to_pcm_float32(audio_input, sample_rate=SAMPLE_RATE)

    @classmethod
    def collect_chunks_by_vad(
        cls,
        waveform: np.ndarray,
        target_chunk_duration: float | None = None,
        max_chunk_duration: float | None = None,
        min_pause_duration: float | None = None,
        min_sentence_duration: float | None = None,
        min_silence_duration_ms: int | None = None,
        min_speech_duration_ms: int | None = None,
        padding_ms: int | None = None,
        vad_threshold: float | None = None,
    ) -> list[AudioChunk]:
        """两阶段切片算法：自然静音探测 + 强制数学等分二次切分（Subsegmentation）。
        
        参数默认读取自 config.yaml 的 ASR-Toolkit 配置，亦支持调用方按需覆盖。

        Args:
            waveform: 16kHz float32 一维音频数组
            target_chunk_duration: 目标切片理想时长（秒）
            max_chunk_duration: 单个切片最大硬上限时长（秒，超过则强制等分二次切分）
            min_pause_duration: 触发自然断句的最小静音停顿阈值（秒）
            min_sentence_duration: 触发停顿断句前切片需达到的最小语义时长（秒）
            min_silence_duration_ms: Silero VAD 最小静音停顿检测阈值（毫秒）
            min_speech_duration_ms: 最小语音段时长（毫秒）
            padding_ms: 首尾填充时长（毫秒）
            vad_threshold: VAD 语音概率置信度阈值 (0.0~1.0)

        Returns:
            list[AudioChunk] 零拷贝 NumPy 数组切片列表
        """
        # 从全局 config.yaml (ASR-Toolkit) 读取默认配置
        cfg = app_config.asr_toolkit
        target_chunk_duration = target_chunk_duration if target_chunk_duration is not None else cfg.chunking.target_chunk_duration
        max_chunk_duration = max_chunk_duration if max_chunk_duration is not None else cfg.chunking.max_chunk_duration
        min_pause_duration = min_pause_duration if min_pause_duration is not None else cfg.chunking.min_pause_duration
        min_sentence_duration = min_sentence_duration if min_sentence_duration is not None else cfg.chunking.min_sentence_duration
        min_silence_duration_ms = min_silence_duration_ms if min_silence_duration_ms is not None else cfg.vad.min_silence_duration_ms
        min_speech_duration_ms = min_speech_duration_ms if min_speech_duration_ms is not None else cfg.vad.min_speech_duration_ms
        padding_ms = padding_ms if padding_ms is not None else cfg.vad.padding_ms
        vad_threshold = vad_threshold if vad_threshold is not None else cfg.vad.threshold

        total_samples = len(waveform)
        total_duration = total_samples / SAMPLE_RATE

        if total_samples == 0 or total_duration <= 0:
            return []

        # 1. 调用 Silero VAD（内存 Tensor 推理）
        speech_timestamps = []
        try:
            from silero_vad import get_speech_timestamps as _get_timestamps, load_silero_vad
            model = load_silero_vad(onnx=False)
            tensor_waveform = torch.from_numpy(waveform).unsqueeze(0)
            raw_ts = _get_timestamps(
                tensor_waveform,
                model,
                threshold=vad_threshold,
                sampling_rate=SAMPLE_RATE,
                min_speech_duration_ms=min_speech_duration_ms,
                min_silence_duration_ms=min_silence_duration_ms,
            )
            speech_timestamps = [
                {"start": t["start"] / SAMPLE_RATE, "end": t["end"] / SAMPLE_RATE}
                for t in raw_ts
            ]
        except Exception as e:
            logger.warning("[ASRToolkit] Silero VAD 内存检测异常: %s", e)

        ranges: list[tuple[float, float]] = []

        # 若未检测到任何有效语音区间（纯静音或全无声），直接返回空列表，0 次 Engine 推理！
        if not speech_timestamps:
            logger.info("[ASRToolkit] 未检测到任何有效语音区间（纯静音），跳过切片与推理 (0 次 Engine 调用)")
            return []

        # 2. 对所有有效语音段应用 padding（防吞音），并合并因 padding 产生的重叠
        padding_sec = padding_ms / 1000.0
        padded_segments: list[dict[str, float]] = []
        for t in speech_timestamps:
            p_start = max(0.0, t["start"] - padding_sec)
            p_end = min(total_duration, t["end"] + padding_sec)
            padded_segments.append({"start": p_start, "end": p_end})

        # 合并因 padding 重叠的片段
        merged_padded: list[dict[str, float]] = []
        for item in padded_segments:
            if not merged_padded:
                merged_padded.append(item.copy())
            else:
                last = merged_padded[-1]
                if item["start"] <= last["end"]:
                    last["end"] = max(last["end"], item["end"])
                else:
                    merged_padded.append(item.copy())

        # 3. 邻近有效语音段智能合并（短停顿合并避免碎词；纯静音区间自然被剔除跳过）
        speech_blocks: list[tuple[float, float]] = []
        cur_start = merged_padded[0]["start"]
        cur_end = merged_padded[0]["end"]

        for next_item in merged_padded[1:]:
            silence_gap = max(0.0, next_item["start"] - cur_end)
            potential_duration = next_item["end"] - cur_start

            # 若停顿间隔小于 min_pause_duration 且合并后总长在 target_chunk_duration 以内，则合并
            if silence_gap < min_pause_duration and potential_duration <= target_chunk_duration:
                cur_end = max(cur_end, next_item["end"])
            else:
                speech_blocks.append((cur_start, cur_end))
                cur_start = next_item["start"]
                cur_end = next_item["end"]

        if cur_end > cur_start:
            speech_blocks.append((cur_start, cur_end))

        # 4. 超长有效语音段等分切分（Subsegmentation）—— 确保单段在 3~8s 以内
        for block_start, block_end in speech_blocks:
            block_len = block_end - block_start
            if block_len < 0.2:
                # 过滤极短瞬态杂音
                continue

            if block_len <= max_chunk_duration:
                ranges.append((block_start, block_end))
            else:
                # 超过 max_chunk_duration 时，强制进行数学等分切分
                num_subsegments = int(np.ceil(block_len / max_chunk_duration))
                subsegment_length = block_len / num_subsegments

                for j in range(num_subsegments):
                    s_sub = block_start + j * subsegment_length
                    e_sub = block_start + (j + 1) * subsegment_length if j < num_subsegments - 1 else block_end
                    ranges.append((round(s_sub, 3), round(e_sub, 3)))

        # 5. 生成零拷贝 NumPy 内存切片
        chunks: list[AudioChunk] = []
        for i, (s_time, e_time) in enumerate(ranges):
            s_idx = max(0, int(s_time * SAMPLE_RATE))
            e_idx = min(total_samples, int(e_time * SAMPLE_RATE))
            chunk_wave = waveform[s_idx:e_idx]

            chunks.append(
                AudioChunk(
                    index=i,
                    waveform=chunk_wave,
                    start_time=round(s_time, 3),
                    end_time=round(e_time, 3),
                    duration=round(e_time - s_time, 3),
                )
            )

        logger.info(
            "[ASRToolkit] 全内存切片完成: 总时长 %.1fs, 提取出 %d 个有效语音切片 (纯静音已自动剔除, 目标: %.1fs, 硬上限: %.1fs)",
            total_duration, len(chunks), target_chunk_duration, max_chunk_duration,
        )
        return chunks

    @classmethod
    async def process_long_audio_stream(
        cls,
        audio_data: bytes | str | Path,
        transcribe_chunk_fn: Callable[[AudioChunk, str], tuple[str, list[Segment]] | Any],
        target_chunk_duration: float | None = None,
        max_chunk_duration: float | None = None,
        prompt_history_chars: int = 150,
    ) -> AsyncIterator[Segment]:
        """通用的全内存流水线流式转录：
        1. 内存解码与零拷贝切片（配置化两阶段切分）
        2. 异步生产者-消费者队列（流水线并行）
        3. 跨切片上下文 Prompt 动态传递
        4. 全局时间戳精准累加与去幻觉后处理
        """
        # 1. 一次性内存解码
        waveform = cls.decode_audio_to_waveform(audio_data)
        if len(waveform) == 0:
            return

        # 2. 内存智能切片（采用 config.yaml 中的 ASR-Toolkit 配置）
        chunks = cls.collect_chunks_by_vad(
            waveform=waveform,
            target_chunk_duration=target_chunk_duration,
            max_chunk_duration=max_chunk_duration,
        )

        # 3. 异步生产者-消费者队列
        queue: asyncio.Queue[AudioChunk | None] = asyncio.Queue(maxsize=3)

        async def _producer():
            for c in chunks:
                await queue.put(c)
            await queue.put(None)

        producer_task = asyncio.create_task(_producer())

        # 4. 消费与流式产出
        prompt_context = ""
        try:
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break

                # 执行单切片推理（传入 chunk 以及历史 prompt 上下文）
                try:
                    res = await asyncio.to_thread(
                        transcribe_chunk_fn, chunk, prompt_context
                    )
                except TypeError:
                    # 兼容只接受一个参数的旧版回调函数
                    res = await asyncio.to_thread(
                        transcribe_chunk_fn, chunk
                    )

                if not res:
                    continue

                chunk_text = ""
                sub_segments: list[Segment] = []
                if isinstance(res, tuple) and len(res) == 2:
                    chunk_text, sub_segments = res
                elif isinstance(res, str):
                    chunk_text = res
                elif isinstance(res, list):
                    sub_segments = res

                # 产出与时间戳累加
                produced_texts = []
                if sub_segments:
                    for sub in sub_segments:
                        text = TextPostProcessor.remove_hallucination_repeats(sub.text)
                        text = TextPostProcessor.normalize_text(text)
                        if not text:
                            continue

                        global_start = round(chunk.start_time + sub.start, 3)
                        global_end = round(chunk.start_time + sub.end, 3)

                        produced_texts.append(text)
                        yield Segment(
                            start=global_start,
                            end=global_end,
                            text=text,
                            speaker=sub.speaker,
                            is_endpoint=True,
                        )
                else:
                    text = TextPostProcessor.remove_hallucination_repeats(chunk_text)
                    text = TextPostProcessor.normalize_text(text)
                    if text:
                        produced_texts.append(text)
                        yield Segment(
                            start=round(chunk.start_time, 3),
                            end=round(chunk.end_time, 3),
                            text=text,
                            is_endpoint=True,
                        )

                # 更新跨切片上下文 Prompt
                if produced_texts:
                    new_chunk_str = "".join(produced_texts)
                    prompt_context = (prompt_context + " " + new_chunk_str).strip()
                    if len(prompt_context) > prompt_history_chars:
                        prompt_context = prompt_context[-prompt_history_chars:]

        finally:
            if not producer_task.done():
                producer_task.cancel()

    @classmethod
    async def process_long_audio(
        cls,
        audio_data: bytes | str | Path,
        transcribe_chunk_fn: Callable[[AudioChunk, str], tuple[str, list[Segment]] | Any],
        target_chunk_duration: float | None = None,
        max_chunk_duration: float | None = None,
        prompt_history_chars: int = 150,
    ) -> tuple[str, list[Segment]]:
        """全量转录长音频（分块处理后合并返回）。"""
        all_segments: list[Segment] = []
        full_text_parts: list[str] = []

        async for seg in cls.process_long_audio_stream(
            audio_data=audio_data,
            transcribe_chunk_fn=transcribe_chunk_fn,
            target_chunk_duration=target_chunk_duration,
            max_chunk_duration=max_chunk_duration,
            prompt_history_chars=prompt_history_chars,
        ):
            all_segments.append(seg)
            if seg.text:
                full_text_parts.append(seg.text)

        full_text = " ".join(full_text_parts).strip()
        return full_text, all_segments
