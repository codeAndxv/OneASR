"""Paths and filesystem directory resolution for OneASR.

Adheres to Ollama-style ~/.oneasr unified user workspace convention.
Supports customization via environment variables (ONEASR_HOME, ONEASR_MODELS_DIR).
"""

from __future__ import annotations

import os
from pathlib import Path

# Project root directory for internal assets and fallback paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def get_oneasr_home() -> Path:
    """Return the base directory for OneASR user configuration and data (~/.oneasr by default)."""
    env_home = os.getenv("ONEASR_HOME")
    if env_home and env_home.strip():
        return Path(env_home.strip()).expanduser().resolve()
    return (Path.home() / ".oneasr").resolve()


def get_models_dir() -> Path:
    """Return the root directory where downloaded ASR model weights are stored."""
    env_models = os.getenv("ONEASR_MODELS_DIR")
    if env_models and env_models.strip():
        return Path(env_models.strip()).expanduser().resolve()
    return (get_oneasr_home() / "models").resolve()


def get_settings_path() -> Path:
    """Return the path to settings.json containing user preferences."""
    return get_oneasr_home() / "settings.json"


def get_logs_dir() -> Path:
    """Return the directory for rotating server logs."""
    return get_oneasr_home() / "logs"


def get_downloads_dir() -> Path:
    """Return the temporary directory for media downloads and extraction."""
    return get_oneasr_home() / "downloads"


def ensure_directories() -> None:
    """Ensure all core runtime directories exist on startup."""
    for directory in [get_oneasr_home(), get_models_dir(), get_logs_dir(), get_downloads_dir()]:
        directory.mkdir(parents=True, exist_ok=True)
