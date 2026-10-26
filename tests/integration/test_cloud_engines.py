"""云端 ASR 引擎真实集成测试（OpenAI 等）。

运行方式：
    OPENAI_API_KEY=sk-xxx uv run pytest tests/integration/test_cloud_engines.py -v -s
"""

import os
import pytest

from server.core.config import EngineConfig

pytestmark = pytest.mark.integration


async def test_openai_cloud_engine(sample_en_wav_bytes: bytes):
    """测试 OpenAI Whisper 云端 API 识别。"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("未设置 OPENAI_API_KEY 环境变量，跳过 OpenAI 云端集成测试")

    from server.engines.openai_engine import OpenAIEngine

    config = EngineConfig(
        "openai-whisper",
        {
            "engine": "openai",
            "type": "cloud",
            "model_name": "whisper-1",
            "api_key": api_key,
        },
        None,
    )
    engine = OpenAIEngine(config)
    text, segments = await engine.transcribe_file(sample_en_wav_bytes)
    assert isinstance(text, str)
    assert len(text.strip()) > 0

