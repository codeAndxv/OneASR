import numpy as np
import pytest
from app.utils.asr_toolkit import ASRToolkit, AudioChunk


def test_collect_chunks_pure_silence():
    """测试纯静音音频输入时，不产生任何切片（0 次 Engine 调用）。"""
    # 3 秒全 0 纯静音
    silence = np.zeros(16000 * 3, dtype=np.float32)
    chunks = ASRToolkit.collect_chunks_by_vad(
        waveform=silence,
        target_chunk_duration=6.0,
        max_chunk_duration=8.0,
    )
    assert len(chunks) == 0


def test_subsegmentation_on_long_speech(monkeypatch):
    """测试当 VAD 检出一段 25s 的超长连续人声时，自动等分切分为不超过 8s 的多个小段。"""
    dummy_waveform = np.ones(16000 * 25, dtype=np.float32)

    import silero_vad

    def mock_get_speech_timestamps(*args, **kwargs):
        return [{"start": 0, "end": 16000 * 25}]

    monkeypatch.setattr(silero_vad, "get_speech_timestamps", mock_get_speech_timestamps)

    chunks = ASRToolkit.collect_chunks_by_vad(
        waveform=dummy_waveform,
        target_chunk_duration=6.0,
        max_chunk_duration=8.0,
    )

    # 25s / 8.0s -> ceil(25/8) = 4 个切片，每段 6.25s
    assert len(chunks) == 4
    for c in chunks:
        assert c.duration <= 8.0
        assert c.duration >= 6.0

    assert chunks[0].start_time == 0.0
    assert chunks[-1].end_time == 25.0
