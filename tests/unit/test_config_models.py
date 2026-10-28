"""测试 EngineConfig 配置解析、驱动解耦与云端/本地多模型驱动映射机制。"""

import pytest

from server.core.config import EngineConfig

pytestmark = pytest.mark.unit


def test_local_engine_config_parsing():
    """验证本地引擎 EngineConfig 构造与字段解析。"""
    stream_cfg = EngineConfig(
        "my-stream",
        {
            "enable": True,
            "driver": "xasr",
            "keep_alive": -1,
            "load": {
                "model_name": "test/stream-repo",
                "sample_rate": 16000,
            },
            "capabilities": {
                "categories": ["RealtimeASR"],
                "languages": ["zh", "en"],
            },
        },
        default_keep_alive=300,
        is_cloud=False,
    )
    assert stream_cfg.name == "my-stream"
    assert stream_cfg.driver == "xasr"
    assert stream_cfg.engine_name == "xasr"
    assert stream_cfg.is_cloud is False
    assert stream_cfg.keep_alive == -1
    assert "RealtimeASR" in stream_cfg.categories

    whisper_cfg = EngineConfig(
        "my-whisper-large",
        {
            "enable": True,
            "driver": "whisper",
            "keep_alive": 600,
            "load": {
                "model_name": "Systran/faster-whisper-large-v3",
                "device": "cpu",
            },
            "capabilities": {
                "categories": ["FileASR"],
                "languages": ["zh", "en", "ja"],
            },
        },
        default_keep_alive=300,
        is_cloud=False,
    )
    assert whisper_cfg.name == "my-whisper-large"
    assert whisper_cfg.driver == "whisper"
    assert whisper_cfg.engine_name == "whisper"
    assert whisper_cfg.is_cloud is False
    assert whisper_cfg.keep_alive == 600


def test_cloud_engine_config_parsing():
    """验证云端引擎 EngineConfig 构造与字段展平。"""
    groq_cfg = EngineConfig(
        "groq/whisper-large-v3",
        {
            "enable": True,
            "driver": "openai",
            "type": "cloud",
            "provider": "groq-cloud",
            "api_key": "gsk_secret_123",
            "base_url": "https://api.groq.com/openai/v1",
            "timeout": 15,
            "model_name": "whisper-large-v3",
            "remote_model": "whisper-large-v3",
            "categories": ["FileASR"],
            "languages": ["zh", "en"],
            "keep_alive": -1,
            "preload": False,
        },
        default_keep_alive=-1,
        is_cloud=True,
    )
    assert groq_cfg.name == "groq/whisper-large-v3"
    assert groq_cfg.is_cloud is True
    assert groq_cfg.type == "cloud"
    assert groq_cfg.api_key == "gsk_secret_123"
    assert groq_cfg.base_url == "https://api.groq.com/openai/v1"
    assert groq_cfg.engine_name == "openai"
    assert groq_cfg.model_name == "whisper-large-v3"


def test_driver_alias_mapping():
    """验证驱动别名 (faster-whisper, qwen-asr, openai-compatible) 自动映射到标准模型系列。"""
    c1 = EngineConfig("test-whisper", {"driver": "faster-whisper"})
    assert c1.driver == "faster-whisper"
    assert c1.engine_name == "whisper"

    c2 = EngineConfig("test-qwen", {"driver": "qwen-asr"})
    assert c2.driver == "qwen-asr"
    assert c2.engine_name == "qwen"

    c3 = EngineConfig("test-openai", {"driver": "openai-compatible"})
    assert c3.driver == "openai-compatible"
    assert c3.engine_name == "openai"
