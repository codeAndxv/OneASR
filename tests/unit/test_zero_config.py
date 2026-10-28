"""Unit tests for OneASR zero-config runtime and filesystem model discovery."""

import json
from pathlib import Path
import pytest

from server.core.config import AppConfig
from server.core.manifest import BUILTIN_MODELS, get_manifest
from server.core.paths import get_models_dir, get_oneasr_home, get_settings_path
from server.core.scanner import scan_all_models

pytestmark = pytest.mark.unit


def test_zero_config_initialization(tmp_path, monkeypatch):
    """Verify that AppConfig initializes cleanly without any configuration file."""
    # Isolate user home to a temporary directory
    fake_home = tmp_path / "fake_home"
    monkeypatch.setenv("ONEASR_HOME", str(fake_home))
    monkeypatch.setenv("ONEASR_API_KEY", "env-secret-key")

    app_cfg = AppConfig()

    # 1. Directory creation
    assert fake_home.exists()
    assert (fake_home / "models").exists()

    # 2. API key from environment variable
    assert app_cfg.api_key == "env-secret-key"

    # 3. Built-in models populated dynamically
    for model_id in BUILTIN_MODELS:
        assert model_id in app_cfg.providers
        cfg = app_cfg.providers[model_id]
        assert cfg.name == model_id

    # 4. Alias resolution
    turbo_cfg = app_cfg.get_provider_config("turbo")
    assert turbo_cfg.name == "whisper-large-v3-turbo"

    sense_cfg = app_cfg.get_provider_config("sensevoice")
    assert sense_cfg.name == "sensevoice-small"


def test_atomic_settings_persistence(tmp_path, monkeypatch):
    """Verify that save_settings safely writes JSON to settings.json."""
    fake_home = tmp_path / "fake_home"
    monkeypatch.setenv("ONEASR_HOME", str(fake_home))

    app_cfg = AppConfig()
    app_cfg.save_settings({"port": 8899, "default_model": "whisper-large-v3-turbo"})

    settings_file = get_settings_path()
    assert settings_file.is_file()

    with open(settings_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["port"] == 8899
    assert data["default_model"] == "whisper-large-v3-turbo"


def test_manifest_definitions():
    """Verify built-in manifest integrity."""
    sense = get_manifest("sensevoice-small")
    assert sense is not None
    assert sense.driver == "funasr"
    assert "RealtimeASR" in sense.categories
    assert "FileASR" in sense.categories

    xasr = get_manifest("xasr-zh-en")
    assert xasr is not None
    assert xasr.driver == "xasr"
    assert xasr.preload is False
    assert xasr.keep_alive == 600
