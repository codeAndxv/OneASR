"""Integration test fixtures — loads built-in Public Domain English speech audio & video."""

from pathlib import Path
import pytest

from tests.helpers.audio_factory import (
    EN_SPEECH_LONG_MP3,
    EN_SPEECH_SHORT_WAV,
    EN_VIDEO_MP4,
    get_fixture_path,
    load_fixture_media,
)


@pytest.fixture(scope="session")
def sample_en_wav_bytes() -> bytes:
    """15s Public Domain English speech WAV (16kHz, mono, PCM16)."""
    return load_fixture_media(EN_SPEECH_SHORT_WAV)


@pytest.fixture(scope="session")
def sample_en_long_audio_bytes() -> bytes:
    """120s (2-min) Public Domain English speech MP3 for long-audio VAD chunking & streaming."""
    return load_fixture_media(EN_SPEECH_LONG_MP3)


@pytest.fixture(scope="session")
def sample_en_video_bytes() -> bytes:
    """60s (1-min) Public Domain English speech MP4 video."""
    return load_fixture_media(EN_VIDEO_MP4)


@pytest.fixture(scope="session")
def sample_en_video_path() -> Path:
    """Path to the 60s Public Domain MP4 video fixture."""
    return get_fixture_path(EN_VIDEO_MP4)
