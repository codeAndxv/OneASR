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

from app.models.schemas import Segment

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
        pcm_16 = (np.clip(self.waveform, -1.0, 1.0) * 32767.0).astype(np.int16)
        with io.BytesIO() as bio:
            with wave.open(bio, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(pcm_16.tobytes())
            return bio.getvalue()

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
        ffmpeg_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
        ]

        if isinstance(audio_input, (str, Path)):
            ffmpeg_cmd.extend(["-i", str(audio_input)])
            input_bytes = None
        else:
            ffmpeg_cmd.extend(["-i", "pipe:0"])
            input_bytes = audio_input

        ffmpeg_cmd.extend([
            "-f", "f32le",
            "-acodec", "pcm_f32le",
            "-ac", "1",
            "-ar", str(SAMPLE_RATE),
            "pipe:1",
        ])

        try:
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE if input_bytes is not None else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout_data, stderr_data = process.communicate(input=input_bytes)
            if process.returncode != 0:
                err_msg = stderr_data.decode("utf-8", errors="ignore")
                raise RuntimeError(f"FFmpeg 解码失败 (code {process.returncode}): {err_msg}")

            audio_np = np.frombuffer(stdout_data, dtype=np.float32).copy()
            if audio_np.size == 0:
                logger.warning("[ASRToolkit] 解码出的音频为空")
                return np.zeros(0, dtype=np.float32)

            return audio_np
        except Exception as e:
            logger.error("[ASRToolkit] 音频内存解码异常: %s", e)
            raise

    @classmethod
    def collect_chunks_by_vad(
        cls,
        waveform: np.ndarray,
        max_chunk_duration: float = 12.0,
        min_pause_duration: float = 0.5,
        min_sentence_duration: float = 2.0,
        min_silence_duration_ms: int = 300,
        min_speech_duration_ms: int = 250,
        padding_ms: int = 150,
    ) -> list[AudioChunk]:
        """借鉴 faster-whisper 的 collect_chunks 算法，在内存中进行防碎片化且兼顾自然停顿的智能语音切片。

        Args:
            waveform: 16kHz float32 一维音频数组
            max_chunk_duration: 单个切片最大目标时长（秒）
            min_pause_duration: 触发自然断句的最小静音停顿阈值（秒）
            min_sentence_duration: 触发停顿断句前切片需达到的最小语义时长（秒）
            min_silence_duration_ms: Silero VAD 最小静音停顿检测阈值（毫秒）
            min_speech_duration_ms: 最小语音段时长（毫秒）
            padding_ms: 首尾填充时长（毫秒）

        Returns:
            list[AudioChunk] 零拷贝 NumPy 数组切片列表
        """
        total_samples = len(waveform)
        total_duration = total_samples / SAMPLE_RATE

        # 1. 调用 Silero VAD（内存 Tensor 推理）
        speech_timestamps = []
        try:
            from silero_vad import get_speech_timestamps as _get_timestamps, load_silero_vad
            model = load_silero_vad(onnx=False)
            tensor_waveform = torch.from_numpy(waveform).unsqueeze(0)
            raw_ts = _get_timestamps(
                tensor_waveform,
                model,
                threshold=0.5,
                sampling_rate=SAMPLE_RATE,
                min_speech_duration_ms=min_speech_duration_ms,
                min_silence_duration_ms=min_silence_duration_ms,
            )
            speech_timestamps = [
                {"start": t["start"] / SAMPLE_RATE, "end": t["end"] / SAMPLE_RATE}
                for t in raw_ts
            ]
        except Exception as e:
            logger.warning("[ASRToolkit] Silero VAD 内存检测异常，回退为均匀切片: %s", e)

        # 2. 如果无语音区间检测，按 max_chunk_duration 进行固定切片
        ranges: list[tuple[float, float]] = []
        if not speech_timestamps:
            cur = 0.0
            while cur < total_duration:
                end = min(cur + max_chunk_duration, total_duration)
                ranges.append((cur, end))
                cur = end
        else:
            # 3. 智能合并算法 (Silence Gap & Max Duration Aware)
            padding_sec = padding_ms / 1000.0
            padded_ts = []
            for t in speech_timestamps:
                p_start = max(0.0, t["start"] - padding_sec)
                p_end = min(total_duration, t["end"] + padding_sec)
                padded_ts.append({"start": p_start, "end": p_end})

            # 先合并重叠的 padded 片段
            merged_raw: list[dict[str, float]] = []
            for item in padded_ts:
                if not merged_raw:
                    merged_raw.append(item.copy())
                else:
                    last = merged_raw[-1]
                    if item["start"] <= last["end"]:
                        last["end"] = max(last["end"], item["end"])
                    else:
                        merged_raw.append(item.copy())

            cur_start = merged_raw[0]["start"]
            cur_end = merged_raw[0]["end"]

            for next_t in merged_raw[1:]:
                silence_gap = max(0.0, next_t["start"] - cur_end)
                cur_dur = cur_end - cur_start

                # 判定是否在当前停顿处断句：
                # 条件 1：若并入下一段后总时长将超过 max_chunk_duration
                # 条件 2：两句之间存在自然静音停顿 (silence_gap >= min_pause_duration) 且当前已有一定语义时长 (cur_dur >= min_sentence_duration)
                should_split = (
                    (next_t["end"] - cur_start > max_chunk_duration)
                    or (silence_gap >= min_pause_duration and cur_dur >= min_sentence_duration)
                )

                if should_split:
                    ranges.append((cur_start, cur_end))
                    cur_start = next_t["start"]
                    cur_end = next_t["end"]
                else:
                    cur_end = max(cur_end, next_t["end"])

            if cur_end > cur_start:
                ranges.append((cur_start, min(cur_end, total_duration)))

        # 4. 生成零拷贝 NumPy 内存切片
        chunks: list[AudioChunk] = []
        for i, (s_time, e_time) in enumerate(ranges):
            s_idx = max(0, int(s_time * SAMPLE_RATE))
            e_idx = min(total_samples, int(e_time * SAMPLE_RATE))
            chunk_wave = waveform[s_idx:e_idx]

            chunks.append(
                AudioChunk(
                    index=i,
                    waveform=chunk_wave,
                    start_time=s_time,
                    end_time=e_time,
                    duration=e_time - s_time,
                )
            )

        logger.info(
            "[ASRToolkit] 全内存切片完成: 总时长 %.1fs, 共 %d 个切片 (目标上限 %.1fs/段, 零磁盘写入)",
            total_duration, len(chunks), max_chunk_duration,
        )
        return chunks

    @classmethod
    async def process_long_audio_stream(
        cls,
        audio_data: bytes | str | Path,
        transcribe_chunk_fn: Callable[[AudioChunk, str], tuple[str, list[Segment]] | Any],
        max_chunk_duration: float = 12.0,
        prompt_history_chars: int = 150,
    ) -> AsyncIterator[Segment]:
        """通用的全内存流水线流式转录：
        1. 内存解码与零拷贝切片
        2. 异步生产者-消费者队列（流水线并行）
        3. 跨切片上下文 Prompt 动态传递
        4. 全局时间戳精准累加与去幻觉后处理
        """
        # 1. 一次性内存解码
        waveform = cls.decode_audio_to_waveform(audio_data)
        if len(waveform) == 0:
            return

        # 2. 内存智能切片
        chunks = cls.collect_chunks_by_vad(
            waveform=waveform,
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
        max_chunk_duration: float = 12.0,
        prompt_history_chars: int = 150,
    ) -> tuple[str, list[Segment]]:
        """全量转录长音频（分块处理后合并返回）。"""
        all_segments: list[Segment] = []
        full_text_parts: list[str] = []

        async for seg in cls.process_long_audio_stream(
            audio_data=audio_data,
            transcribe_chunk_fn=transcribe_chunk_fn,
            max_chunk_duration=max_chunk_duration,
            prompt_history_chars=prompt_history_chars,
        ):
            all_segments.append(seg)
            if seg.text:
                full_text_parts.append(seg.text)

        full_text = " ".join(full_text_parts).strip()
        return full_text, all_segments
