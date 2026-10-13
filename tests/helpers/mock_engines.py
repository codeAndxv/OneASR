"""Reusable Mock ASR Engine and StreamSession factories."""

from unittest.mock import AsyncMock, MagicMock
from server.schemas.audio import Segment


class MockStreamSession:
    """模拟流式识别会话（兼容 X-ASR / FunASR / Whisper 流式接口）。"""

    def __init__(self, text: str = "你好世界。"):
        self.text = text
        self._partial_sent = False

    def accept_audio(self, audio_bytes: bytes, input_sample_rate: int | None = None):
        pass

    def decode(self):
        pass

    def get_partial_result(self) -> str:
        if not self._partial_sent:
            self._partial_sent = True
            return self.text
        return ""

    def get_full_text(self) -> str:
        return self.text

    def is_endpoint(self) -> bool:
        return True

    def reset_endpoint(self):
        pass

    def finalize(self) -> str:
        return self.text


def make_mock_engine(
    text: str = "你好，测试语音转录。",
    segments: list[Segment] | None = None,
) -> MagicMock:
    """构造标准化的模拟 ASR 引擎，支持文件同步识别、SSE 流式识别与实时流会话。"""
    if segments is None:
        segments = [Segment(start=0.0, end=1.0, text=text)]

    mock = MagicMock()
    mock.transcribe_file = AsyncMock(return_value=(text, segments))

    async def _mock_file_stream(audio_data: bytes, **kwargs):
        for seg in segments:
            yield seg

    async def _mock_stream(data, **kwargs):
        yield {"type": "transcript.text.segment", "text": text}
        yield {"type": "transcript.text.done", "text": text}

    mock.transcribe_file_stream = _mock_file_stream
    mock.transcribe_stream = _mock_stream
    mock.create_stream_session.return_value = MockStreamSession(text=text)
    return mock
