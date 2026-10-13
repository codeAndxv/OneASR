"""Global test configuration and lightweight shared fixtures."""

import os

# 在导入任何 server 模块之前强制标记测试环境，确保数据库指向独立的 oneasr_test.db
os.environ["ONEASR_TESTING"] = "1"

import pytest
from fastapi.testclient import TestClient

from server.core.config import app_config
from server.main import app
from tests.helpers.audio_factory import make_pcm_bytes, make_wav_bytes, make_wav_io
from tests.helpers.mock_engines import MockStreamSession, make_mock_engine

TEST_API_KEY = "oneasr-key"
app_config.api_key = TEST_API_KEY


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """标准 Bearer 鉴权请求头。"""
    return {"Authorization": f"Bearer {TEST_API_KEY}"}


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient 实例。"""
    return TestClient(app)


@pytest.fixture
def wav_bytes() -> bytes:
    """1 秒 16kHz 单声道静音 WAV 字节流。"""
    return make_wav_bytes(duration_sec=1.0)


@pytest.fixture
def sine_wav_bytes() -> bytes:
    """1 秒 16kHz 440Hz 正弦波 WAV 字节流。"""
    return make_wav_bytes(duration_sec=1.0, frequency=440.0)


@pytest.fixture
def pcm_bytes() -> bytes:
    """1 秒 16kHz 单声道静音 PCM 字节流。"""
    return make_pcm_bytes(duration_sec=1.0)


@pytest.fixture
def wav_io():
    """可直接上传的 WAV BytesIO 对象。"""
    return make_wav_io(duration_sec=1.0)


@pytest.fixture
def mock_engine():
    """通用模拟 ASR 引擎。"""
    return make_mock_engine()


@pytest.fixture
def mock_stream_session():
    """通用模拟流式识别会话。"""
    return MockStreamSession()
