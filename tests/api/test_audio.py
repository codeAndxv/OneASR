"""统一的语音识别 API 测试（参考 OpenAI 格式）。"""

import io
import json
import wave

import pytest


from unittest.mock import AsyncMock, MagicMock, patch

from server.schemas.audio import Segment


def _make_mock_engine():
    mock = MagicMock()
    mock.transcribe_file = AsyncMock(return_value=("你好，测试语音转录。", [Segment(start=0.0, end=1.0, text="你好，测试语音转录。")]))

    async def _mock_stream(data, **kwargs):
        yield {"type": "transcript.text.segment", "text": "你好，测试语音转录。"}
        yield {"type": "transcript.text.done", "text": "你好，测试语音转录。"}

    mock.transcribe_stream = _mock_stream
    return mock


class TestAudioModelsEndpoint:
    """测试 /v1/models 端点。"""

    def test_list_models(self, client):
        """列出可用模型。"""
        resp = client.get("/v1/models", headers={"Authorization": "Bearer oneasr-key"})
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
        """没有 API Key 应该返回 401 authentication_error。"""
        resp = client.get("/v1/models")
        assert resp.status_code == 401
        data = resp.json()
        assert "error" in data
        assert data["error"]["type"] == "authentication_error"


class TestAudioTranscriptionsEndpoint:
    """测试 /v1/audio/transcriptions 端点。"""

    def test_create_transcription_no_params(self, client):
        """没有 file 应该返回 400 参数校验失败。"""
        resp = client.post(
            "/v1/audio/transcriptions",
            headers={"Authorization": "Bearer oneasr-key"},
            data={"model": "faster-whisper"},
        )
        assert resp.status_code == 400
        assert "error" in resp.json()
        assert resp.json()["error"]["type"] == "invalid_request_error"

    def test_create_transcription_with_file(self, client):
        """上传文件进行识别。"""
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
                data={"model": "faster-whisper", "response_format": "json"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "text" in data

    def test_create_transcription_with_file_text_format(self, client):
        """上传文件进行识别，返回纯文本格式。"""
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
                data={"model": "faster-whisper", "response_format": "text"},
            )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/plain; charset=utf-8"

    def test_create_transcription_file_too_large(self, client):
        """上传超过 25MB 的文件应该返回 400 invalid_request_error, param='file', code='file_too_large'。"""
        large_content = b"\x00" * (25 * 1024 * 1024 + 1)  # 25MB + 1 byte
        files = {"file": ("large.wav", io.BytesIO(large_content), "audio/wav")}

        resp = client.post(
            "/v1/audio/transcriptions",
            headers={"Authorization": "Bearer oneasr-key"},
            files=files,
            data={"model": "faster-whisper"},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == "file_too_large"
        assert data["error"]["param"] == "file"

    def test_create_transcription_stream(self, client):
        """测试流式识别（stream=true）。"""
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
        assert "text/event-stream" in resp.headers["content-type"]

        # 解析 SSE 事件
        events = []
        for line in resp.text.strip().split("\n"):
            line = line.strip()
            if line.startswith("data: "):
                payload = line[len("data: "):]
                events.append(json.loads(payload))

        assert len(events) >= 1
        assert events[-1].get("type") == "transcript.text.done"

    def test_create_transcription_mp4_file(self, client):
        """上传 MP4 文件进行识别。"""
        fake_mp4_content = b"\x00" * 1024
        files = {"file": ("test_video.mp4", io.BytesIO(fake_mp4_content), "video/mp4")}

        with patch("server.api.audio.get_engine", return_value=_make_mock_engine()):
            resp = client.post(
                "/v1/audio/transcriptions",
                headers={"Authorization": "Bearer oneasr-key"},
                files=files,
                data={"model": "faster-whisper", "response_format": "json"},
            )
        assert resp.status_code != 422
        assert resp.status_code in [200, 400, 500]

    def test_create_transcription_m4a_file(self, client):
        """上传 M4A 文件进行识别。"""
        fake_m4a_content = b"\x00" * 1024
        files = {"file": ("test_audio.m4a", io.BytesIO(fake_m4a_content), "audio/mp4")}

        with patch("server.api.audio.get_engine", return_value=_make_mock_engine()):
            resp = client.post(
                "/v1/audio/transcriptions",
                headers={"Authorization": "Bearer oneasr-key"},
                files=files,
                data={"model": "faster-whisper", "response_format": "json"},
            )
        assert resp.status_code != 422
        assert resp.status_code in [200, 400, 500]


# ============================================================
# 真实文件集成测试（需要本地存在测试文件）
# ============================================================

TEST_MP4_FILE = "/Users/dudu/Files/Video/clips/lyj_03_01_part003.mp4"


@pytest.mark.integration
class TestRealFileTranscription:
    """使用真实 MP4 文件测试转录。"""

    def _upload_file(self, client) -> str:
        """上传测试文件，返回 file_id。"""
        from pathlib import Path

        mp4_path = Path(TEST_MP4_FILE)
        with open(mp4_path, "rb") as f:
            file_data = f.read()

        resp = client.post(
            "/v1/file/upload",
            headers={"Authorization": "Bearer oneasr-key"},
            files={"file": (mp4_path.name, io.BytesIO(file_data), "video/mp4")},
        )
        assert resp.status_code == 200
        return resp.json()["file_id"]

    def test_transcribe_real_mp4(self, client):
        """通过真实 MP4 文件测试异步转录任务。"""
        from pathlib import Path

        mp4_path = Path(TEST_MP4_FILE)
        if not mp4_path.exists():
            pytest.skip(f"测试文件不存在: {TEST_MP4_FILE}")

        file_id = self._upload_file(client)

        resp = client.post(
            "/v1/file/transcriptions",
            headers={"Authorization": "Bearer oneasr-key"},
            json={
                "file_uuid": file_id,
                "model": "faster-whisper",
                "response_format": "verbose_json",
            },
        )

        assert resp.status_code == 200, f"创建任务失败: {resp.json()}"
        data = resp.json()
        assert "task_id" in data
        assert data["status"] in ["pending", "processing", "completed"]

    def test_transcribe_real_mp4_json(self, client):
        """通过真实 MP4 文件测试 JSON 任务创建。"""
        from pathlib import Path

        mp4_path = Path(TEST_MP4_FILE)
        if not mp4_path.exists():
            pytest.skip(f"测试文件不存在: {TEST_MP4_FILE}")

        file_id = self._upload_file(client)

        resp = client.post(
            "/v1/file/transcriptions",
            headers={"Authorization": "Bearer oneasr-key"},
            json={
                "file_uuid": file_id,
                "model": "faster-whisper",
                "response_format": "json",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data

    def test_transcribe_real_mp4_text(self, client):
        """通过真实 MP4 文件测试 text 任务创建。"""
        from pathlib import Path

        mp4_path = Path(TEST_MP4_FILE)
        if not mp4_path.exists():
            pytest.skip(f"测试文件不存在: {TEST_MP4_FILE}")

        file_id = self._upload_file(client)

        resp = client.post(
            "/v1/file/transcriptions",
            headers={"Authorization": "Bearer oneasr-key"},
            json={
                "file_uuid": file_id,
                "model": "faster-whisper",
                "response_format": "text",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
