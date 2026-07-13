"""测试所有 ASR 引擎。"""

import asyncio
import os
from pathlib import Path

from app.core.config import app_config, EngineConfig
from app.utils.format import format_output

TEST_FILE = Path("/Volumes/µ/files/DuRT/DuRT-增加文本校正功能.mp4")


async def test_engine(engine_name: str, engine, audio_data: bytes):
    """测试单个引擎。"""
    print(f"\n{'='*60}")
    print(f"测试引擎: {engine_name}")
    print(f"{'='*60}")

    print("开始识别...")
    text, segments = await engine.transcribe_file(audio_data)

    print(f"\n识别结果 ({len(segments)} 个片段):")
    print(f"{'-'*40}")
    for seg in segments:
        if seg.start == 0 and seg.end == 0:
            print(f"  {seg.text}")
        else:
            print(f"  [{seg.start:.2f}s - {seg.end:.2f}s] {seg.text}")

    print(f"\n完整文本:\n{text}")

    # 输出 SRT 格式
    print(f"\nSRT 格式:")
    print(f"{'-'*40}")
    srt_content = format_output(text, segments, "srt")
    print(srt_content)

    return text, segments


async def test_whisper():
    """测试 Whisper 引擎。"""
    from app.engines.whisper_engine import WhisperEngine

    config = app_config.get_provider_config("whisper1")
    config.model_name = "medium"  # 使用 medium 模型
    engine = WhisperEngine(config)
    return await test_engine("faster-whisper", engine, TEST_FILE.read_bytes())


async def test_firered():
    """测试 FireRedASR 引擎。"""
    from app.engines.firered_engine import FireRedEngine

    config = app_config.get_provider_config("firered")
    engine = FireRedEngine(config)
    return await test_engine("firered", engine, TEST_FILE.read_bytes())


async def test_openai():
    """测试 OpenAI 引擎。"""
    from app.engines.openai_engine import OpenAIEngine

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("跳过 OpenAI 测试：未设置 OPENAI_API_KEY")
        return None

    config = EngineConfig("openai-whisper", {
        "engine": "openai",
        "type": "cloud",
        "model_name": "whisper-1",
        "api_key": api_key,
    }, None)
    engine = OpenAIEngine(config)
    return await test_engine("openai", engine, TEST_FILE.read_bytes())


async def test_mimo(api_key: str = None, base_url: str = None, model_name: str = None):
    """测试小米 MiMo 引擎。"""
    from app.engines.mimo_engine import MiMoEngine

    api_key = api_key or os.environ.get("MIMO_API_KEY")
    if not api_key:
        print("跳过 MiMo 测试：未提供 API Key")
        return None

    config = EngineConfig("mimo", {
        "engine": "mimo",
        "type": "cloud",
        "model_name": model_name or "mimo-v2.5",
        "api_key": api_key,
        "base_url": base_url or "https://token-plan-sgp.xiaomimimo.com/v1",
    }, None)
    engine = MiMoEngine(config)
    return await test_engine("mimo", engine, TEST_FILE.read_bytes())


async def main():
    """测试所有引擎。"""
    if not TEST_FILE.exists():
        print(f"测试文件不存在: {TEST_FILE}")
        return

    print(f"测试文件: {TEST_FILE.name} ({TEST_FILE.stat().st_size / 1024 / 1024:.1f}MB)")

    # 测试本地引擎
    await test_whisper()
    await test_firered()

    # 测试云端引擎
    await test_openai()
    # MiMo 需要单独提供 API Key


if __name__ == "__main__":
    asyncio.run(main())
