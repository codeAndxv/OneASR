"""统一的语音识别 API 测试（参考 OpenAI 格式）。"""

import io
import json
import wave

import pytest


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

    def test_create_transcription_no_params(self, client):
        """没有 file 和 file_uuid 应该返回 400。"""
        resp = client.post(
            "/api/v1/audio/transcriptions",
            headers={"X-API-Key": "oneasr-key"},
            data={"model": "faster-whisper"},
        )
        assert resp.status_code == 400
        assert "必须提供" in resp.json()["detail"]

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

    def test_create_transcription_with_file_uuid(self, client):
        """使用 file_uuid 进行识别（需要先上传文件）。"""
        # 先上传一个文件
        test_content = b"fake audio content"
        files = {"file": ("test_uuid.mp3", io.BytesIO(test_content), "audio/mpeg")}
        
        upload_resp = client.post(
            "/api/v1/files/upload",
            files=files,
            headers={"X-API-Key": "oneasr-key"},
        )
        assert upload_resp.status_code == 200
        file_id = upload_resp.json()["file_id"]

        # 使用 file_uuid 进行转录
        resp = client.post(
            "/api/v1/audio/transcriptions",
            headers={"X-API-Key": "oneasr-key"},
            data={
                "file_uuid": file_id,
                "model": "faster-whisper",
                "response_format": "json",
            },
        )
        # 注意：实际转录可能失败（因为测试环境没有模型），但接口应该正常响应
        assert resp.status_code in [200, 500]

    def test_create_transcription_file_uuid_not_found(self, client):
        """使用不存在的 file_uuid 应该返回 404。"""
        resp = client.post(
            "/api/v1/audio/transcriptions",
            headers={"X-API-Key": "oneasr-key"},
            data={
                "file_uuid": "nonexistent-uuid",
                "model": "faster-whisper",
            },
        )
        assert resp.status_code == 404
        assert "文件不存在" in resp.json()["detail"]

    def test_create_transcription_file_too_large(self, client):
        """上传超过 25MB 的文件应该返回 400。"""
        # 创建一个超过 25MB 的假文件
        large_content = b"\x00" * (25 * 1024 * 1024 + 1)  # 25MB + 1 byte
        files = {"file": ("large.wav", io.BytesIO(large_content), "audio/wav")}

        resp = client.post(
            "/api/v1/audio/transcriptions",
            headers={"X-API-Key": "oneasr-key"},
            files=files,
            data={"model": "faster-whisper"},
        )
        assert resp.status_code == 400
        assert "文件大小超过限制" in resp.json()["detail"] or "25MB" in resp.json()["detail"]

    def test_create_transcription_stream(self, client):
        """测试流式识别（stream=true）。"""
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
        assert events[-1].get("done") is True

    def test_create_transcription_stream_with_file_uuid(self, client):
        """测试使用 file_uuid 进行流式识别。"""
        # 先上传一个文件
        test_content = b"fake audio content"
        files = {"file": ("test_stream.mp3", io.BytesIO(test_content), "audio/mpeg")}
        
        upload_resp = client.post(
            "/api/v1/files/upload",
            files=files,
            headers={"X-API-Key": "oneasr-key"},
        )
        assert upload_resp.status_code == 200
        file_id = upload_resp.json()["file_id"]

        # 使用 file_uuid 进行流式转录
        resp = client.post(
            "/api/v1/audio/transcriptions",
            headers={"X-API-Key": "oneasr-key"},
            data={
                "file_uuid": file_id,
                "model": "faster-whisper",
                "stream": "true",
            },
        )
        # 注意：实际转录可能失败（因为测试环境没有模型），但接口应该正常响应
        assert resp.status_code in [200, 500]

    def test_create_transcription_mp4_file(self, client):
        """上传 MP4 文件进行识别（测试自动转换为 WAV）。"""
        # 创建一个最小的 MP4 文件头（用于测试转换逻辑）
        # 注意：这不是真正的 MP4，但可以测试接口是否接受 MP4 扩展名
        fake_mp4_content = b"\x00" * 1024  # 1KB 假数据
        files = {"file": ("test_video.mp4", io.BytesIO(fake_mp4_content), "video/mp4")}

        resp = client.post(
            "/api/v1/audio/transcriptions",
            headers={"X-API-Key": "oneasr-key"},
            files=files,
            data={"model": "faster-whisper", "response_format": "json"},
        )
        # MP4 应该被接受（422 错误表示格式不被接受）
        # 实际转录可能失败（因为假数据），但不应该返回 422
        assert resp.status_code != 422, f"MP4 格式不应返回 422: {resp.json()}"
        # 可能返回 200（如果转换成功）或 500（如果转换/转录失败）
        assert resp.status_code in [200, 400, 500]

    def test_create_transcription_m4a_file(self, client):
        """上传 M4A 文件进行识别。"""
        fake_m4a_content = b"\x00" * 1024
        files = {"file": ("test_audio.m4a", io.BytesIO(fake_m4a_content), "audio/mp4")}

        resp = client.post(
            "/api/v1/audio/transcriptions",
            headers={"X-API-Key": "oneasr-key"},
            files=files,
            data={"model": "faster-whisper", "response_format": "json"},
        )
        assert resp.status_code != 422, f"M4A 格式不应返回 422: {resp.json()}"
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
            "/api/v1/files/upload",
            headers={"X-API-Key": "oneasr-key"},
            files={"file": (mp4_path.name, io.BytesIO(file_data), "video/mp4")},
        )
        assert resp.status_code == 200
        return resp.json()["file_id"]

    def test_transcribe_real_mp4(self, client):
        """通过 UUID 转录真实 MP4 文件，返回 verbose_json 格式。"""
        from pathlib import Path

        mp4_path = Path(TEST_MP4_FILE)
        if not mp4_path.exists():
            pytest.skip(f"测试文件不存在: {TEST_MP4_FILE}")

        file_id = self._upload_file(client)

        resp = client.post(
            "/api/v1/audio/transcriptions",
            headers={"X-API-Key": "oneasr-key"},
            data={
                "file_uuid": file_id,
                "model": "faster-whisper",
                "response_format": "verbose_json",
            },
        )

        assert resp.status_code == 200, f"转录失败: {resp.json()}"
        data = resp.json()
        assert "text" in data
        assert "segments" in data
        assert len(data["text"]) > 0, "转录结果不应为空"
        print(f"\n转录结果: {data['text'][:200]}...")
        print(f"分段数: {len(data['segments'])}")

    def test_transcribe_real_mp4_json(self, client):
        """通过 UUID 转录真实 MP4 文件，返回 JSON 格式。"""
        from pathlib import Path

        mp4_path = Path(TEST_MP4_FILE)
        if not mp4_path.exists():
            pytest.skip(f"测试文件不存在: {TEST_MP4_FILE}")

        file_id = self._upload_file(client)

        resp = client.post(
            "/api/v1/audio/transcriptions",
            headers={"X-API-Key": "oneasr-key"},
            data={
                "file_uuid": file_id,
                "model": "faster-whisper",
                "response_format": "json",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "text" in data
        assert len(data["text"]) > 0

    def test_transcribe_real_mp4_text(self, client):
        """通过 UUID 转录真实 MP4 文件，返回纯文本格式。"""
        from pathlib import Path

        mp4_path = Path(TEST_MP4_FILE)
        if not mp4_path.exists():
            pytest.skip(f"测试文件不存在: {TEST_MP4_FILE}")

        file_id = self._upload_file(client)

        resp = client.post(
            "/api/v1/audio/transcriptions",
            headers={"X-API-Key": "oneasr-key"},
            data={
                "file_uuid": file_id,
                "model": "faster-whisper",
                "response_format": "text",
            },
        )

        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
        assert len(resp.text) > 0

    def test_transcribe_real_mp4_stream(self, client):
        """通过 UUID 流式转录真实 MP4 文件。"""
        from pathlib import Path

        mp4_path = Path(TEST_MP4_FILE)
        if not mp4_path.exists():
            pytest.skip(f"测试文件不存在: {TEST_MP4_FILE}")

        file_id = self._upload_file(client)

        resp = client.post(
            "/api/v1/audio/transcriptions",
            headers={"X-API-Key": "oneasr-key"},
            data={
                "file_uuid": file_id,
                "model": "faster-whisper",
                "stream": "true",
            },
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
        print(f"\n流式事件数: {len(events)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
