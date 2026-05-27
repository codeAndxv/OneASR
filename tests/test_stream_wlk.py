"""测试 WhisperLiveKit 流式识别接口。"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _make_mock_front_data():
    """创建一个模拟的 FrontData 对象。"""
    mock = MagicMock()
    mock.to_dict.return_value = {
        "status": "active_transcription",
        "lines": [
            {"speaker": 1, "text": "你好世界", "start": "0:00:01.00", "end": "0:00:03.00"},
        ],
        "buffer_transcription": "测试",
        "buffer_diarization": "",
        "buffer_translation": "",
        "remaining_time_transcription": 0.0,
        "remaining_time_diarization": 0.0,
    }
    return mock


class TestStreamEndpoint:
    """测试 /ws/transcribe/stream 端点。"""

    def test_non_wlk_engine_returns_error(self, client):
        """使用非 wlk 引擎时应返回错误。"""
        with client.websocket_connect("/ws/transcribe/stream?engine=faster-whisper") as ws:
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "不支持流式识别" in data["error"]

    def test_invalid_engine_returns_error(self, client):
        """使用不存在的引擎时应返回错误。"""
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/transcribe/stream?engine=nonexistent") as ws:
                pass

    @patch("app.engines.wlk_engine.WLKEngine.create_audio_processor")
    def test_wlk_engine_config_message(self, mock_create, client):
        """连接后应收到 config 消息。"""
        mock_processor = MagicMock()
        mock_processor.is_pcm_input = False
        mock_processor.create_tasks = AsyncMock(return_value=self._empty_generator())
        mock_processor.process_audio = AsyncMock()
        mock_processor.cleanup = AsyncMock()
        mock_create.return_value = mock_processor

        with client.websocket_connect("/ws/transcribe/stream?engine=wlk") as ws:
            config_msg = ws.receive_json()
            assert config_msg["type"] == "config"
            assert "useAudioWorklet" in config_msg
            assert config_msg["mode"] == "full"

    @patch("app.engines.wlk_engine.WLKEngine.create_audio_processor")
    def test_wlk_engine_sends_audio(self, mock_create, client):
        """发送音频数据后应收到识别结果。"""
        mock_front_data = _make_mock_front_data()

        async def result_gen():
            yield mock_front_data

        mock_processor = MagicMock()
        mock_processor.is_pcm_input = False
        mock_processor.create_tasks = AsyncMock(return_value=result_gen())
        mock_processor.process_audio = AsyncMock()
        mock_processor.cleanup = AsyncMock()
        mock_create.return_value = mock_processor

        with client.websocket_connect("/ws/transcribe/stream?engine=wlk") as ws:
            # 读取 config 消息
            ws.receive_json()

            # 发送音频数据
            ws.send_bytes(b"\x00\x01" * 100)

            # 读取结果
            result = ws.receive_json()
            assert result["status"] == "active_transcription"
            assert len(result["lines"]) == 1
            assert result["lines"][0]["text"] == "你好世界"
            assert result["lines"][0]["speaker"] == 1
            assert result["buffer_transcription"] == "测试"

    @staticmethod
    async def _empty_generator():
        """空的异步生成器，用于模拟无结果的情况。"""
        if False:
            yield


class TestWLKStreamResponse:
    """测试 WLKStreamResponse 数据模型。"""

    def test_schema_structure(self):
        """验证响应模型的字段。"""
        from app.models.schemas import WLKStreamResponse, StreamLine

        line = StreamLine(speaker=1, text="你好", start="0:00:01.00", end="0:00:02.00")
        resp = WLKStreamResponse(
            status="active_transcription",
            lines=[line],
            buffer_transcription="测试",
        )

        data = resp.model_dump()
        assert data["status"] == "active_transcription"
        assert len(data["lines"]) == 1
        assert data["lines"][0]["text"] == "你好"
        assert data["lines"][0]["speaker"] == 1
        assert data["buffer_transcription"] == "测试"

    def test_schema_defaults(self):
        """验证默认值。"""
        from app.models.schemas import WLKStreamResponse

        resp = WLKStreamResponse()
        assert resp.status == "active_transcription"
        assert resp.lines == []
        assert resp.buffer_transcription == ""
        assert resp.error == ""


class TestWLKEngineConfig:
    """测试 WLKEngine 配置构建。"""

    def test_build_wlk_config_defaults(self):
        """验证默认配置构建。"""
        from app.engines.wlk_engine import WLKEngine
        from app.core.config import EngineConfig

        config = EngineConfig("wlk", {
            "type": "local",
            "model_name": "base",
            "backend": "auto",
            "backend_policy": "simulstreaming",
            "language": "auto",
            "vac": True,
            "diarization": False,
            "pcm_input": False,
        }, model_dir=None)

        engine = WLKEngine(config)
        wlk_config = engine._build_wlk_config()

        assert wlk_config.model_size == "base"
        assert wlk_config.backend == "auto"
        assert wlk_config.backend_policy == "simulstreaming"
        assert wlk_config.lan == "auto"
        assert wlk_config.vac is True
        assert wlk_config.diarization is False
        assert wlk_config.pcm_input is False

    def test_build_wlk_config_with_language_override(self):
        """验证语言覆盖。"""
        from app.engines.wlk_engine import WLKEngine
        from app.core.config import EngineConfig

        config = EngineConfig("wlk", {
            "type": "local",
            "model_name": "base",
            "language": "auto",
        }, model_dir=None)

        engine = WLKEngine(config)
        wlk_config = engine._build_wlk_config(language="zh")

        assert wlk_config.lan == "zh"

    def test_parse_time(self):
        """验证时间解析。"""
        from app.engines.wlk_engine import WLKEngine

        assert WLKEngine._parse_time("0:00:05.30") == 5.30
        assert WLKEngine._parse_time("1:30:00.00") == 5400.0
        assert WLKEngine._parse_time("0:05:10.50") == 310.50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
