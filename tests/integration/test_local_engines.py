"""本地离线 ASR 引擎真实模型加载与语音/视频转录测试（基于仓库内置 Public Domain 英文演讲素材）。

运行方式：
    uv run pytest tests/integration/test_local_engines.py -v -s
"""

import gc
import time
import pytest

from server.core.config import app_config
from server.utils.audio_converter import AudioConverter
from server.utils.format import format_output

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def _release_memory():
    """主动触发垃圾回收与 PyTorch 显存/统一内存缓存释放，防止多模型同时驻留撑爆内存。"""
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            torch.mps.empty_cache()
    except Exception:
        pass


def _print_benchmark(
    engine_name: str,
    audio_duration: float,
    load_time: float,
    infer_time: float,
    text: str,
    segment_count: int,
):
    rtf = infer_time / audio_duration if audio_duration > 0 else 0.0
    print(
        f"\n┌──────────────────────────────────────────────────────────────\n"
        f"│ [Benchmark] 引擎: {engine_name}\n"
        f"│ 音频时长: {audio_duration:.2f}s | 模型加载: {load_time:.2f}s | 推理耗时: {infer_time:.2f}s | RTF: {rtf:.3f}x\n"
        f"│ 分段数量: {segment_count} | 识别结果: {text}\n"
        f"└──────────────────────────────────────────────────────────────"
    )


async def test_xasr_real_stream_inference(sample_en_wav_bytes: bytes):
    """实测 X-ASR (sherpa-onnx) 流式模型加载与分块实时语音识别。"""
    cfg = app_config.get_provider_config("xasr")
    tokens_path = cfg.resolve_path(getattr(cfg, "tokens_path", ""))
    if not tokens_path or not tokens_path.exists():
        pytest.skip(f"本地 X-ASR 模型文件不存在: {tokens_path}")

    from server.engines.xasr_engine import XASREngine

    pcm16_bytes = AudioConverter.decode_to_pcm16_bytes(sample_en_wav_bytes, sample_rate=16000)
    audio_duration = AudioConverter.get_audio_duration(pcm16_bytes, sample_rate=16000)
    assert audio_duration > 10.0

    t0 = time.perf_counter()
    engine = XASREngine(cfg)
    load_time = time.perf_counter() - t0

    try:
        t_infer = time.perf_counter()
        session = engine.create_stream_session(input_sample_rate=16000)

        # 按 160ms (5120 字节) 模拟实时音频流分块送入
        chunk_bytes = int(16000 * 2 * 0.16)
        partials = []
        collected_sentences = []

        for offset in range(0, len(pcm16_bytes), chunk_bytes):
            chunk = pcm16_bytes[offset : offset + chunk_bytes]
            session.accept_audio(chunk, input_sample_rate=16000)
            session.decode()
            delta = session.get_partial_result()
            if delta:
                partials.append(delta)
            if session.is_endpoint():
                utt = session.get_full_text()
                if utt:
                    collected_sentences.append(utt)
                session.reset_endpoint()

        tail_text = session.finalize()
        if tail_text:
            collected_sentences.append(tail_text)

        full_text = " ".join(collected_sentences).strip()
        infer_time = time.perf_counter() - t_infer

        _print_benchmark(
            "xasr (sherpa-onnx)",
            audio_duration,
            load_time,
            infer_time,
            full_text,
            len(collected_sentences),
        )

        assert len(full_text) > 0, "X-ASR 真实语音流式识别结果不应为空"
    finally:
        del engine
        _release_memory()


async def test_faster_whisper_real_inference(
    sample_en_wav_bytes: bytes,
    sample_en_video_bytes: bytes,
):
    """实测 Faster-Whisper (medium) 真实模型加载、15s 英文音频转录及 60s MP4 视频流式分段转录。"""
    cfg = app_config.get_provider_config("faster-whisper")
    model_dir = cfg.resolve_path(cfg.model_path) if cfg.model_path else None
    if not model_dir or not model_dir.exists():
        pytest.skip(f"本地 Faster-Whisper 模型不存在: {model_dir}")

    from server.engines.whisper_engine import WhisperEngine

    short_duration = AudioConverter.get_audio_duration(sample_en_wav_bytes)

    t0 = time.perf_counter()
    engine = WhisperEngine(cfg)
    load_time = time.perf_counter() - t0

    try:
        # 1. 15s 英文演讲 WAV 整段识别
        t_short = time.perf_counter()
        text, segments = await engine.transcribe_file(sample_en_wav_bytes, language="en")
        short_infer_time = time.perf_counter() - t_short

        _print_benchmark(
            "faster-whisper (15s wav)",
            short_duration,
            load_time,
            short_infer_time,
            text,
            len(segments),
        )

        assert len(text.strip()) > 0
        assert "library" in text.lower() or "everybody" in text.lower()
        assert len(segments) >= 2
        for seg in segments:
            assert 0.0 <= seg.start <= seg.end

        srt_content = format_output(text, segments, "srt")
        assert "-->" in srt_content

        # 2. 60s MP4 视频文件自动提取音轨 + VAD 流式分段识别
        t_vid = time.perf_counter()
        video_segments = []
        async for seg in engine.transcribe_file_stream(sample_en_video_bytes, language="en"):
            video_segments.append(seg)
        vid_infer_time = time.perf_counter() - t_vid
        video_text = " ".join(s.text.strip() for s in video_segments).strip()

        _print_benchmark(
            "faster-whisper-stream (60s mp4 video)",
            60.0,
            0.0,
            vid_infer_time,
            video_text,
            len(video_segments),
        )

        assert len(video_text) > 50
        assert len(video_segments) >= 5
    finally:
        del engine
        _release_memory()


async def test_qwen_asr_real_inference(sample_en_wav_bytes: bytes):
    """实测 Qwen3-ASR-1.7B 本地模型加载与 15s 英文演讲转录。"""
    cfg = app_config.get_provider_config("qwen")
    model_dir = cfg.resolve_path(cfg.model_path) if cfg.model_path else None
    if not model_dir or not model_dir.exists():
        pytest.skip(f"本地 Qwen3-ASR 模型不存在: {model_dir}")

    try:
        import qwen_asr  # noqa: F401
    except ImportError:
        pytest.skip("当前环境未安装 qwen_asr，跳过 Qwen3-ASR 实测")

    from server.engines.qwen_engine import QwenEngine

    duration = AudioConverter.get_audio_duration(sample_en_wav_bytes)

    t0 = time.perf_counter()
    engine = QwenEngine(cfg)
    load_time = time.perf_counter() - t0

    try:
        t_infer = time.perf_counter()
        text, segments = await engine.transcribe_file(sample_en_wav_bytes)
        infer_time = time.perf_counter() - t_infer

        _print_benchmark(
            "Qwen3-ASR-1.7B (15s wav)",
            duration,
            load_time,
            infer_time,
            text,
            len(segments),
        )

        assert len(text.strip()) > 0, "Qwen3-ASR 识别文本不应为空"
        assert "library" in text.lower() or "everybody" in text.lower()
        assert len(segments) >= 1
    finally:
        del engine
        _release_memory()


async def test_funasr_real_inference(sample_en_wav_bytes: bytes):
    """实测 FunASR (SenseVoiceSmall + fsmn-vad) 本地模型加载与 15s 英文演讲转录。"""
    cfg = app_config.get_provider_config("funasr")
    model_dir = cfg.resolve_path(cfg.model_path) if cfg.model_path else None
    if not model_dir or not model_dir.exists():
        pytest.skip(f"本地 FunASR 模型不存在: {model_dir}")

    try:
        import funasr  # noqa: F401
    except ImportError:
        pytest.skip("当前环境未安装 funasr，跳过 FunASR 实测")

    from server.engines.funasr_engine import FunASREngine

    duration = AudioConverter.get_audio_duration(sample_en_wav_bytes)

    t0 = time.perf_counter()
    engine = FunASREngine(cfg, lazy_load=False)
    load_time = time.perf_counter() - t0

    try:
        t_infer = time.perf_counter()
        text, segments = await engine.transcribe_file(sample_en_wav_bytes, language="en")
        infer_time = time.perf_counter() - t_infer

        _print_benchmark(
            "funasr (SenseVoiceSmall, 15s wav)",
            duration,
            load_time,
            infer_time,
            text,
            len(segments),
        )

        assert len(text.strip()) > 0, "FunASR 识别文本不应为空"
        assert "<|" not in text, "FunASR SenseVoice 富文本标签应被清理干净"
        assert "library" in text.lower() or "everybody" in text.lower()
        assert len(segments) >= 1
    finally:
        engine.unload()
        del engine
        _release_memory()

