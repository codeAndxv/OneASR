"""测试 SSE 流式识别 API。"""

import io
import json
import wave
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _parse_sse_events(text: str) -> list[dict]:
    """解析 SSE 响应文本为事件列表。"""
    events = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            payload = line[len("data: "):]
            events.append(json.loads(payload))
    return events


from server.schemas.audio import Segment


def _make_mock_engine():
    mock = MagicMock()
    mock.transcribe_file = AsyncMock(return_value=("你好，测试语音转录。", []))

    async def _mock_stream(data, **kwargs):
        yield Segment(start=0.0, end=1.0, text="你好，测试语音转录。")

    mock.transcribe_file_stream = _mock_stream
    return mock


class TestStreamingTranscription:
    """测试 /v1/audio/transcriptions 流式识别端点。"""

    def test_stream_no_file(self, client):
        """没有上传文件应该返回 400。"""
        resp = client.post(
            "/v1/audio/transcriptions",
            headers={"Authorization": "Bearer oneasr-key"},
            data={"model": "faster-whisper", "stream": "true"},
        )
        assert resp.status_code == 400

    def test_stream_with_file(self, client):
        """上传文件进行流式识别。"""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 16000)  # 1 秒静音
        buf.seek(0)

        with patch("server.api.audio.get_engine", return_value=_make_mock_engine()):
            resp = client.post(
                "/v1/audio/transcriptions",
                headers={"Authorization": "Bearer oneasr-key"},
                files={"file": ("test.wav", buf, "audio/wav")},
                data={"model": "faster-whisper", "stream": "true"},
            )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        events = _parse_sse_events(resp.text)
        assert len(events) >= 1
        assert events[-1].get("type") == "transcript.text.done"

    def test_stream_event_format(self, client):
        """验证 SSE 事件格式。"""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 16000)
        buf.seek(0)

        with patch("server.api.audio.get_engine", return_value=_make_mock_engine()):
            resp = client.post(
                "/v1/audio/transcriptions",
                headers={"Authorization": "Bearer oneasr-key"},
                files={"file": ("test.wav", buf, "audio/wav")},
                data={"model": "faster-whisper", "stream": "true"},
            )
        assert resp.status_code == 200

        events = _parse_sse_events(resp.text)
        assert len(events) >= 2

        # 验证增量事件格式
        delta_evt = events[0]
        assert "delta" in delta_evt
        assert delta_evt.get("type") == "transcript.text.delta"

        # 最后一个事件应该是 done
        assert events[-1].get("type") == "transcript.text.done"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
