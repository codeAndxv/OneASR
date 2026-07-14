"""测试 WhisperLiveKit 引擎和数据模型。"""

from unittest.mock import MagicMock

import pytest

from app.engines.whisperlivekit_engine import WhisperLiveKitEngine


class TestWhisperLiveKitStreamResponse:
    """测试 WhisperLiveKitStreamResponse 数据模型。"""

    def test_schema_structure(self):
        from app.models.schemas import WhisperLiveKitStreamResponse, StreamLine

        line = StreamLine(speaker=1, text="你好", start="0:00:01.00", end="0:00:02.00")
        resp = WhisperLiveKitStreamResponse(
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
        from app.models.schemas import WhisperLiveKitStreamResponse

        resp = WhisperLiveKitStreamResponse()
        assert resp.status == "active_transcription"
        assert resp.lines == []
        assert resp.buffer_transcription == ""
        assert resp.error == ""


class TestWhisperLiveKitEngineConfig:
    """测试 WhisperLiveKitEngine 配置构建。"""

    def test_build_whisperlivekit_config_defaults(self):
        from app.engines.whisperlivekit_engine import WhisperLiveKitEngine
        from app.core.config import EngineConfig

        config = EngineConfig("wlk-live", {
            "engine": "whisperlivekit",
            "type": "local",
            "model_name": "base",
            "backend": "auto",
            "backend_policy": "simulstreaming",
            "language": "auto",
            "vac": True,
            "diarization": False,
            "pcm_input": False,
        }, model_dir=None)

        engine = WhisperLiveKitEngine(config)
        whisperlivekit_config = engine._build_config()

        assert whisperlivekit_config.model_size == "base"
        assert whisperlivekit_config.backend == "auto"
        assert whisperlivekit_config.backend_policy == "simulstreaming"
        assert whisperlivekit_config.lan == "auto"
        assert whisperlivekit_config.vac is True
        assert whisperlivekit_config.diarization is False
        assert whisperlivekit_config.pcm_input is False

    def test_build_whisperlivekit_config_with_language_override(self):
        from app.engines.whisperlivekit_engine import WhisperLiveKitEngine
        from app.core.config import EngineConfig

        config = EngineConfig("wlk-live", {
            "engine": "whisperlivekit",
            "type": "local",
            "model_name": "base",
            "language": "auto",
        }, model_dir=None)

        engine = WhisperLiveKitEngine(config)
        whisperlivekit_config = engine._build_config(language="zh")

        assert whisperlivekit_config.lan == "zh"

    def test_parse_time(self):
        assert WhisperLiveKitEngine._parse_time("0:00:05.30") == 5.30
        assert WhisperLiveKitEngine._parse_time("1:30:00.00") == 5400.0
        assert WhisperLiveKitEngine._parse_time("0:05:10.50") == 310.50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
