"""WhisperEngine 单元测试（Mock 底层 WhisperModel）。"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from server.core.config import EngineConfig
from server.engines.whisper_engine import WhisperEngine

pytestmark = pytest.mark.unit


class MockWord:
    def __init__(self, word, start, end, probability=0.95):
        self.word = word
        self.start = start
        self.end = end
        self.probability = probability


class MockSegment:
    def __init__(self, text, start, end, words=None, avg_logprob=-0.15):
        self.text = text
        self.start = start
        self.end = end
        self.words = words or []
        self.avg_logprob = avg_logprob


async def test_whisper_transcribe_file_robustness(tmp_path: Path):
    cfg = EngineConfig(
        "faster-whisper",
        {
            "model_name": "Systran/faster-whisper-tiny",
            "model_path": str(tmp_path),
            "device": "cpu",
            "compute_type": "float32",
        },
    )

    mock_model = MagicMock()
    words = [
        MockWord("Hello", 0.0, 0.5, 0.98),
        MockWord("world", 0.5, 1.0, 0.96),
    ]
    seg = MockSegment("Hello world", 0.0, 1.0, words=words)
    mock_model.transcribe.return_value = ([seg], None)

    with patch("server.engines.whisper_engine.WhisperModel", return_value=mock_model):
        engine = WhisperEngine(cfg)
        text, segments = await engine.transcribe_file(b"fake-wav-bytes", language="en")

        assert text == "Hello world"
        assert len(segments) == 1
        assert segments[0].text == "Hello world"
        assert segments[0].words is not None
        assert len(segments[0].words) == 2
        assert segments[0].words[0].word == "Hello"
        assert segments[0].words[1].word == "world"

        call_kwargs = mock_model.transcribe.call_args[1]
        assert call_kwargs.get("vad_filter") is True
        assert call_kwargs.get("condition_on_previous_text") is False
        assert call_kwargs.get("word_timestamps") is True
        assert call_kwargs.get("compression_ratio_threshold") == 2.4
        assert call_kwargs.get("beam_size") == 5


async def test_whisper_transcribe_file_stream_robustness(tmp_path: Path):
    cfg = EngineConfig(
        "faster-whisper",
        {
            "model_name": "Systran/faster-whisper-tiny",
            "model_path": str(tmp_path),
            "device": "cpu",
            "compute_type": "float32",
        },
    )

    mock_model = MagicMock()
    words = [MockWord("Streaming", 0.0, 0.8, 0.95)]
    seg = MockSegment("Streaming", 0.0, 0.8, words=words)
    mock_model.transcribe.return_value = ([seg], None)

    with patch("server.engines.whisper_engine.WhisperModel", return_value=mock_model):
        engine = WhisperEngine(cfg)
        stream_results = []
        async for s in engine.transcribe_file_stream(b"fake-wav-bytes", language="en"):
            stream_results.append(s)

        assert len(stream_results) == 1
        assert stream_results[0].text == "Streaming"
        assert stream_results[0].words is not None
        assert stream_results[0].words[0].word == "Streaming"


async def test_whisper_parameter_passthrough_and_language_normalization(tmp_path: Path):
    cfg = EngineConfig(
        "faster-whisper",
        {
            "model_name": "Systran/faster-whisper-tiny",
            "model_path": str(tmp_path),
            "device": "cpu",
            "compute_type": "float32",
        },
    )

    mock_model = MagicMock()
    seg = MockSegment("OneASR", 0.0, 1.0, words=[MockWord("OneASR", 0.0, 1.0)])
    mock_model.transcribe.return_value = ([seg], None)

    with patch("server.engines.whisper_engine.WhisperModel", return_value=mock_model):
        engine = WhisperEngine(cfg)
        await engine.transcribe_file(
            b"fake-wav-bytes",
            language="zh-CN",
            prompt="OneASR, DuRT",
            temperature=0.2,
            vad_filter=False,
            word_timestamps=False,
        )

        call_kwargs = mock_model.transcribe.call_args[1]
        assert call_kwargs["language"] == "zh"
        assert call_kwargs["initial_prompt"] == "OneASR, DuRT"
        assert call_kwargs["temperature"] == 0.2
        assert call_kwargs["vad_filter"] is False
        assert call_kwargs["word_timestamps"] is False

        # "auto" should normalize to None so Whisper auto-detects language
        mock_model.transcribe.reset_mock()
        mock_model.transcribe.return_value = ([seg], None)
        await engine.transcribe_file(b"fake-wav-bytes", language="auto")
        auto_kwargs = mock_model.transcribe.call_args[1]
        assert auto_kwargs["language"] is None
