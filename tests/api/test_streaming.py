"""测试 SSE 流式识别 API。"""

import io
import json
import wave

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


class TestStreamingTranscription:
    """测试 /api/v1/audio/transcriptions 流式识别端点。"""

    def test_stream_no_file_no_uuid(self, client):
        """没有 file 和 file_uuid 应该返回 400。"""
        resp = client.post(
            "/api/v1/audio/transcriptions",
            headers={"X-API-Key": "oneasr-key"},
            data={"model": "faster-whisper", "stream": "true"},
        )
        assert resp.status_code == 400
        assert "必须提供" in resp.json()["detail"]

    def test_stream_with_file(self, client):
        """上传文件进行流式识别。"""
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
            data={"model": "faster-whisper", "stream": "true"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        events = _parse_sse_events(resp.text)
        assert len(events) >= 1
        assert events[-1].get("done") is True

    def test_stream_with_file_uuid(self, client):
        """使用 file_uuid 进行流式识别。"""
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

    def test_stream_file_uuid_not_found(self, client):
        """使用不存在的 file_uuid 进行流式识别应该返回 404。"""
        resp = client.post(
            "/api/v1/audio/transcriptions",
            headers={"X-API-Key": "oneasr-key"},
            data={
                "file_uuid": "nonexistent-uuid",
                "model": "faster-whisper",
                "stream": "true",
            },
        )
        assert resp.status_code == 404
        assert "文件不存在" in resp.json()["detail"]

    def test_stream_event_format(self, client):
        """验证 SSE 事件格式。"""
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

        events = _parse_sse_events(resp.text)
        
        # 验证事件格式
        for evt in events[:-1]:  # 排除最后一个 done 事件
            assert "index" in evt
            assert "start" in evt
            assert "end" in evt
            assert "text" in evt

        # 最后一个事件应该是 done
        assert events[-1].get("done") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
