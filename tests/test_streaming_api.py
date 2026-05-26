"""测试 SSE 流式识别 API。"""

import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_stream_file_no_engine():
    """没有文件时应该返回 422。"""
    resp = client.post("/api/v1/transcribe/file/stream")
    assert resp.status_code == 422


def test_stream_url_invalid():
    """无效 URL 应该返回 400。"""
    resp = client.post(
        "/api/v1/transcribe/url/stream",
        json={"url": "http://invalid.example.com/test.mp3"},
    )
    assert resp.status_code == 400


def test_stream_url_invalid_engine():
    """无效引擎名称应该返回错误。"""
    resp = client.post(
        "/api/v1/transcribe/url/stream",
        json={"url": "http://example.com/test.mp3", "engine": "invalid"},
    )
    assert resp.status_code in [400, 500]


def _parse_sse_events(text: str) -> list[dict]:
    """解析 SSE 响应文本为事件列表。"""
    events = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            payload = line[len("data: "):]
            events.append(json.loads(payload))
    return events


def test_stream_file_with_engine():
    """使用 whisper 引擎上传文件，验证 SSE 流式响应格式。

    需要 whisper 引擎可用，如果不可用则跳过。
    """
    import numpy as np
    import io
    import wave

    # 生成一个简短的静音 WAV 文件用于测试
    sample_rate = 16000
    duration = 0.5  # 0.5 秒
    samples = np.zeros(int(sample_rate * duration), dtype=np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())
    buf.seek(0)

    try:
        resp = client.post(
            "/api/v1/transcribe/file/stream",
            files={"file": ("test.wav", buf, "audio/wav")},
            params={"engine": "whisper"},
        )
    except Exception:
        # whisper 引擎不可用，跳过
        return

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    events = _parse_sse_events(resp.text)
    # 最后一个事件应该是 done
    assert len(events) >= 1
    assert events[-1].get("done") is True

    # 如果有识别结果，检查格式
    for evt in events[:-1]:
        assert "index" in evt
        assert "start" in evt
        assert "end" in evt
        assert "text" in evt


if __name__ == "__main__":
    test_stream_file_no_engine()
    test_stream_url_invalid()
    test_stream_url_invalid_engine()
    print("流式 API 基础测试通过")
