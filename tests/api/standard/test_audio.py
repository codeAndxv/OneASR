"""OpenAI 标准兼容层音频转录 API 契约测试 (POST /v1/audio/transcriptions)。

包含：
1. 同步转录与参数校验 (JSON, text, verbose_json 等)
2. stream=true SSE 流式输出与事件格式校验
3. 音视频多格式支持与参数透传校验
"""

import io
import json
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.api


def _parse_sse_events(text: str) -> list[dict]:
    """解析 SSE 响应文本为事件列表。"""
    events = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            payload = line[len("data: "):]
            events.append(json.loads(payload))
    return events


class TestAudioTranscriptionsEndpoint:
    """测试 /v1/audio/transcriptions 端点基础调用与参数。"""

    def test_create_transcription_no_params(self, client, auth_headers):
        """没有 file 应该返回 400 参数校验失败。"""
        resp = client.post(
            "/v1/audio/transcriptions",
            headers=auth_headers,
            data={"model": "faster-whisper"},
        )
        assert resp.status_code == 400
        assert "error" in resp.json()
        assert resp.json()["error"]["type"] == "invalid_request_error"

    def test_create_transcription_no_api_key(self, client):
        """没有 API Key 应该返回 401 或 422。"""
        resp = client.post(
            "/v1/audio/transcriptions",
            data={"model": "faster-whisper"},
        )
        assert resp.status_code in [401, 422]

    def test_create_transcription_with_file(self, client, auth_headers, wav_io, mock_engine):
        """上传 WAV 文件进行识别（JSON 格式）。"""
        with patch("server.api.standard.audio.get_engine", return_value=mock_engine):
            resp = client.post(
                "/v1/audio/transcriptions",
                headers=auth_headers,
                files={"file": ("test.wav", wav_io, "audio/wav")},
                data={"model": "faster-whisper", "response_format": "json"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "text" in data
        assert "你好" in data["text"]

    def test_create_transcription_with_file_text_format(self, client, auth_headers, wav_io, mock_engine):
        """上传文件进行识别，返回纯文本格式。"""
        with patch("server.api.standard.audio.get_engine", return_value=mock_engine):
            resp = client.post(
                "/v1/audio/transcriptions",
                headers=auth_headers,
                files={"file": ("test.wav", wav_io, "audio/wav")},
                data={"model": "faster-whisper", "response_format": "text"},
            )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/plain; charset=utf-8"

    def test_create_transcription_file_too_large(self, client, auth_headers):
        """上传超过 25MB 的文件应返回 400 file_too_large。"""
        large_content = b"\x00" * (25 * 1024 * 1024 + 1)
        files = {"file": ("large.wav", io.BytesIO(large_content), "audio/wav")}

        resp = client.post(
            "/v1/audio/transcriptions",
            headers=auth_headers,
            files=files,
            data={"model": "faster-whisper"},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == "file_too_large"
        assert data["error"]["param"] == "file"

    def test_create_transcription_mp4_file(self, client, auth_headers, mock_engine):
        """上传 MP4 文件格式校验通过（非 422）。"""
        fake_mp4_content = b"\x00" * 1024
        files = {"file": ("test_video.mp4", io.BytesIO(fake_mp4_content), "video/mp4")}

        with patch("server.api.standard.audio.get_engine", return_value=mock_engine):
            resp = client.post(
                "/v1/audio/transcriptions",
                headers=auth_headers,
                files=files,
                data={"model": "faster-whisper", "response_format": "json"},
            )
        assert resp.status_code != 422
        assert resp.status_code in [200, 400, 500]

    def test_create_transcription_m4a_file(self, client, auth_headers, mock_engine):
        """上传 M4A 文件格式校验通过（非 422）。"""
        fake_m4a_content = b"\x00" * 1024
        files = {"file": ("test_audio.m4a", io.BytesIO(fake_m4a_content), "audio/mp4")}

        with patch("server.api.standard.audio.get_engine", return_value=mock_engine):
            resp = client.post(
                "/v1/audio/transcriptions",
                headers=auth_headers,
                files=files,
                data={"model": "faster-whisper", "response_format": "json"},
            )
        assert resp.status_code != 422
        assert resp.status_code in [200, 400, 500]

    def test_create_transcription_passes_parameters_to_engine(
        self, client, auth_headers, wav_io, mock_engine
    ):
        """验证 language、prompt、keywords、temperature、chunking_strategy、timestamp_granularities 透传给引擎。"""
        with patch("server.api.standard.audio.get_engine", return_value=mock_engine):
            resp = client.post(
                "/v1/audio/transcriptions",
                headers=auth_headers,
                files={"file": ("test.wav", wav_io, "audio/wav")},
                data={
                    "model": "faster-whisper",
                    "language": "zh",
                    "prompt": "科技播客",
                    "keywords": "OneASR, DuRT",
                    "temperature": "0.2",
                    "chunking_strategy": "none",
                    "timestamp_granularities": "segment",
                },
            )
        assert resp.status_code == 200
        mock_engine.transcribe_file.assert_called_once()
        call_kwargs = mock_engine.transcribe_file.call_args.kwargs
        assert call_kwargs["language"] == "zh"
        assert call_kwargs["prompt"] == "科技播客, OneASR, DuRT"
        assert call_kwargs["temperature"] == 0.2
        assert call_kwargs["vad_filter"] is False
        assert call_kwargs["word_timestamps"] is False


class TestStreamingTranscription:
    """测试 /v1/audio/transcriptions 流式识别端点 (stream=true)。"""

    def test_stream_no_file(self, client, auth_headers):
        """没有上传文件应该返回 400。"""
        resp = client.post(
            "/v1/audio/transcriptions",
            headers=auth_headers,
            data={"model": "faster-whisper", "stream": "true"},
        )
        assert resp.status_code == 400

    def test_stream_with_file(self, client, auth_headers, wav_io, mock_engine):
        """上传文件进行流式识别。"""
        with patch("server.api.standard.audio.get_engine", return_value=mock_engine):
            resp = client.post(
                "/v1/audio/transcriptions",
                headers=auth_headers,
                files={"file": ("test.wav", wav_io, "audio/wav")},
                data={"model": "faster-whisper", "stream": "true"},
            )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        events = _parse_sse_events(resp.text)
        assert len(events) >= 1
        assert events[-1].get("type") == "transcript.text.done"

    def test_stream_event_format(self, client, auth_headers, wav_io, mock_engine):
        """验证 SSE 事件格式。"""
        with patch("server.api.standard.audio.get_engine", return_value=mock_engine):
            resp = client.post(
                "/v1/audio/transcriptions",
                headers=auth_headers,
                files={"file": ("test.wav", wav_io, "audio/wav")},
                data={"model": "faster-whisper", "stream": "true"},
            )
        assert resp.status_code == 200

        events = _parse_sse_events(resp.text)
        assert len(events) >= 2

        delta_evt = events[0]
        assert "delta" in delta_evt
        assert delta_evt.get("type") == "transcript.text.delta"
        assert events[-1].get("type") == "transcript.text.done"

    def test_create_transcription_stream_passes_parameters_to_engine(
        self, client, auth_headers, wav_io, mock_engine
    ):
        """验证 stream=true 时参数同样透传给 transcribe_file_stream。"""
        captured_kwargs = {}
        orig_stream = mock_engine.transcribe_file_stream

        async def _capturing_stream(audio_data: bytes, **kwargs):
            captured_kwargs.update(kwargs)
            async for seg in orig_stream(audio_data, **kwargs):
                yield seg

        mock_engine.transcribe_file_stream = _capturing_stream

        with patch("server.api.standard.audio.get_engine", return_value=mock_engine):
            resp = client.post(
                "/v1/audio/transcriptions",
                headers=auth_headers,
                files={"file": ("test.wav", wav_io, "audio/wav")},
                data={
                    "model": "faster-whisper",
                    "stream": "true",
                    "language": "en",
                    "prompt": "OpenAI",
                    "temperature": "0.0",
                },
            )
        assert resp.status_code == 200
        assert captured_kwargs["language"] == "en"
        assert captured_kwargs["prompt"] == "OpenAI"
        assert captured_kwargs["temperature"] == 0.0


class TestTranscriptionFormats:
    """测试转录格式参数。"""

    def test_transcribe_json_format(self, client, auth_headers, wav_io, mock_engine):
        """测试 JSON 格式输出。"""
        with patch("server.api.standard.audio.get_engine", return_value=mock_engine):
            resp = client.post(
                "/v1/audio/transcriptions",
                headers=auth_headers,
                files={"file": ("test.wav", wav_io, "audio/wav")},
                data={"model": "faster-whisper", "response_format": "json"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "text" in data

    def test_transcribe_verbose_json_format(self, client, auth_headers, wav_io, mock_engine):
        """测试 verbose_json 格式输出。"""
        with patch("server.api.standard.audio.get_engine", return_value=mock_engine):
            resp = client.post(
                "/v1/audio/transcriptions",
                headers=auth_headers,
                files={"file": ("test.wav", wav_io, "audio/wav")},
                data={"model": "faster-whisper", "response_format": "verbose_json"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "text" in data
        assert "segments" in data

    def test_transcribe_text_format(self, client, auth_headers, wav_io, mock_engine):
        """测试纯文本格式输出。"""
        with patch("server.api.standard.audio.get_engine", return_value=mock_engine):
            resp = client.post(
                "/v1/audio/transcriptions",
                headers=auth_headers,
                files={"file": ("test.wav", wav_io, "audio/wav")},
                data={"model": "faster-whisper", "response_format": "text"},
            )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/plain; charset=utf-8"
