"""测试 local-models 与 cloud-providers 配置解析、驱动解耦与云端多模型展平机制。"""

import tempfile
from pathlib import Path
import pytest
import yaml

from cli.model import collect_all_specs
from server.core.config import AppConfig, EngineConfig

pytestmark = pytest.mark.unit


def test_local_models_and_cloud_providers_parsing():
    sample_yaml = {
        "api_key": "test-key",
        "model_manager": {
            "default_keep_alive": 300,
            "max_loaded_models": 3,
        },
        "local-models": {
            "my-stream": {
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
            "my-whisper-large": {
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
        },
        "cloud-providers": {
            "groq-cloud": {
                "enable": True,
                "driver": "openai",
                "connection": {
                    "base_url": "https://api.groq.com/openai/v1",
                    "api_key": "gsk_secret_123",
                    "timeout": 15,
                },
                "models": [
                    {
                        "id": "groq/whisper-large-v3",
                        "remote_name": "whisper-large-v3",
                        "categories": ["FileASR"],
                    },
                    {
                        "id": "groq/whisper-turbo",
                        "remote_name": "whisper-large-v3-turbo",
                        "categories": ["FileASR"],
                    },
                ],
            },
            "disabled-cloud": {
                "enable": False,
                "connection": {
                    "api_key": "dummy",
                },
                "models": [{"id": "should-not-exist"}],
            },
        },
    }

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        yaml.dump(sample_yaml, f)
        cfg_path = Path(f.name)

    try:
        app_cfg = AppConfig(cfg_path)

        # 1. 验证 local_models 与 providers 包含自定义 Model ID
        assert "my-stream" in app_cfg.local_models
        assert "my-whisper-large" in app_cfg.local_models
        assert len(app_cfg.local_models) == 2

        # 驱动名称解析
        stream_cfg = app_cfg.local_models["my-stream"]
        assert stream_cfg.driver == "xasr"
        assert stream_cfg.engine_name == "xasr"
        assert stream_cfg.is_cloud is False
        assert stream_cfg.keep_alive == -1

        whisper_cfg = app_cfg.local_models["my-whisper-large"]
        assert whisper_cfg.driver == "whisper"
        assert whisper_cfg.engine_name == "whisper"
        assert whisper_cfg.is_cloud is False

        # 2. 验证 cloud-providers 一 Key 多模型展平到 providers
        assert "groq/whisper-large-v3" in app_cfg.providers
        assert "groq/whisper-turbo" in app_cfg.providers
        assert "should-not-exist" not in app_cfg.providers

        groq_cfg = app_cfg.providers["groq/whisper-large-v3"]
        assert groq_cfg.is_cloud is True
        assert groq_cfg.type == "cloud"
        assert groq_cfg.api_key == "gsk_secret_123"
        assert groq_cfg.base_url == "https://api.groq.com/openai/v1"
        assert groq_cfg.engine_name == "openai"
        assert groq_cfg.model_name == "whisper-large-v3"

        # 3. 验证短名查找
        found = app_cfg.get_provider_config("whisper-turbo")
        assert found.name == "groq/whisper-turbo"

        # 4. 验证 CLI 只收集本地模型
        specs = collect_all_specs(app_cfg)
        spec_names = [s.provider_name for s in specs]
        assert "my-stream" in spec_names
        assert "my-whisper-large" in spec_names
        assert "groq/whisper-large-v3" not in spec_names
        assert "groq/whisper-turbo" not in spec_names

    finally:
        cfg_path.unlink(missing_ok=True)


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
