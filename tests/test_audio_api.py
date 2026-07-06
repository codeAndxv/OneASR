"""测试统一的语音识别 API 接口（参考 OpenAI 格式）。"""

import io
import json
import wave

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestAudioModelsEndpoint:
    """测试 /api/v1/audio/models 端点。"""

    def test_list_models(self, client):
        """列出可用模型。"""
        resp = client.get("/api/v1/audio/models", headers={"X-API-Key": "oneasr-key"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert "data" in data
        assert len(data["data"]) > 0
        # 检查模型格式
        model = data["data"][0]
        assert "id" in model
        assert "object" in model
        assert model["object"] == "model"

    def test_list_models_without_api_key(self, client):
        """没有 API Key 应该返回 401 或 422。"""
        resp = client.get("/api/v1/audio/models")
        assert resp.status_code in [401, 422]


class TestAudioTranscriptionsEndpoint:
    """测试 /api/v1/audio/transcriptions 端点。"""

    def test_create_transcription_no_file_no_url(self, client):
        """没有 file 和 url 应该返回 400。"""
        resp = client.post(
            "/api/v1/audio/transcriptions",
            headers={"X-API-Key": "oneasr-key"},
            data={"model": "faster-whisper"},
        )
        assert resp.status_code == 400
        assert "file" in resp.json()["detail"] or "url" in resp.json()["detail"]

    def test_create_transcription_invalid_url(self, client):
        """无效 URL 应该返回 400。"""
        resp = client.post(
            "/api/v1/audio/transcriptions",
            headers={"X-API-Key": "oneasr-key"},
            data={
                "url": "http://invalid.example.com/test.mp3",
                "model": "faster-whisper",
            },
        )
        assert resp.status_code == 400

    def test_create_transcription_with_file(self, client):
        """上传文件进行识别。"""
        # 创建一个简单的 WAV 文件
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 16000)  # 1 秒静音
        buf.seek(0)

        resp = client.post(
            "/api/v1/audio/transcriptions",
            headers={"X-API-Key": "oneasr-key"},
            files={"file": ("test.wav", buf, "audio/wav")},
            data={"model": "faster-whisper", "response_format": "json"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "text" in data
        assert "segments" in data
        assert "engine" in data

    def test_create_transcription_with_file_text_format(self, client):
        """上传文件进行识别，返回纯文本格式。"""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 16000)
        buf.seek(0)

        resp = client.post(
            "/api/v1/audio/transcriptions",
            headers={"X-API-Key": "oneasr-key"},
            files={"file": ("test.wav", buf, "audio/wav")},
            data={"model": "faster-whisper", "response_format": "text"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/plain; charset=utf-8"


class TestAudioTranscriptionsStreamEndpoint:
    """测试 /api/v1/audio/transcriptions/stream 端点。"""

    def test_stream_no_file_no_url(self, client):
        """没有 file 和 url 应该返回 400。"""
        resp = client.post(
            "/api/v1/audio/transcriptions/stream",
            headers={"X-API-Key": "oneasr-key"},
            data={"model": "faster-whisper"},
        )
        assert resp.status_code == 400

    def test_stream_invalid_url(self, client):
        """无效 URL 应该返回 400。"""
        resp = client.post(
            "/api/v1/audio/transcriptions/stream",
            headers={"X-API-Key": "oneasr-key"},
            data={
                "url": "http://invalid.example.com/test.mp3",
                "model": "faster-whisper",
            },
        )
        assert resp.status_code == 400

    def test_stream_with_file(self, client):
        """上传文件进行流式识别。"""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 16000)
        buf.seek(0)

        resp = client.post(
            "/api/v1/audio/transcriptions/stream",
            headers={"X-API-Key": "oneasr-key"},
            files={"file": ("test.wav", buf, "audio/wav")},
            data={"model": "faster-whisper"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        # 解析 SSE 事件
        events = []
        for line in resp.text.strip().split("\n"):
            line = line.strip()
            if line.startswith("data: "):
                payload = line[len("data: "):]
                events.append(json.loads(payload))

        assert len(events) >= 1
        assert events[-1].get("done") is True


class TestLegacyEndpoints:
    """测试旧的 API 端点（保持兼容）。"""

    def test_legacy_engines(self, client):
        """旧的引擎列表接口。"""
        resp = client.get("/api/v1/engines", headers={"X-API-Key": "oneasr-key"})
        assert resp.status_code == 200
        data = resp.json()
        assert "default" in data
        assert "engines" in data

    def test_legacy_formats(self, client):
        """旧的格式列表接口。"""
        resp = client.get("/api/v1/formats", headers={"X-API-Key": "oneasr-key"})
        assert resp.status_code == 200
        data = resp.json()
        assert "formats" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
