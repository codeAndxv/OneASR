"""测试 API 接口的格式参数。"""

import io
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


class TestTranscriptionFormats:
    """测试转录格式参数。"""

    def test_transcribe_json_format(self, client):
        """测试 JSON 格式输出。"""
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
            data={"model": "faster-whisper", "response_format": "json"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "text" in data
        assert "segments" in data

    def test_transcribe_text_format(self, client):
        """测试纯文本格式输出。"""
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

    def test_transcribe_no_params(self, client):
        """没有文件应该返回 400。"""
        resp = client.post(
            "/api/v1/audio/transcriptions",
            headers={"X-API-Key": "oneasr-key"},
            data={"model": "faster-whisper"},
        )
        assert resp.status_code == 400
        assert "必须提供" in resp.json()["detail"]

    def test_transcribe_no_api_key(self, client):
        """没有 API Key 应该返回 401 或 422。"""
        resp = client.post(
            "/api/v1/audio/transcriptions",
            data={"model": "faster-whisper"},
        )
        assert resp.status_code in [401, 422]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
