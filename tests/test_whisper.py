"""测试 Whisper 引擎文件识别功能。"""

import asyncio
from pathlib import Path

from app.core.config import app_config
from app.engines.whisper_engine import WhisperEngine

TEST_FILE = Path("/Volumes/µ/files/DuRT/DuRT-增加文本校正功能.mp4")


async def test_transcribe():
    if not TEST_FILE.exists():
        print(f"测试文件不存在: {TEST_FILE}")
        return

    print(f"加载 medium 模型...")
    config = app_config.get_engine_config("whisper")
    config.model_name = "medium"  # 覆盖为 medium 模型
    engine = WhisperEngine(config)

    print(f"读取文件: {TEST_FILE.name} ({TEST_FILE.stat().st_size / 1024 / 1024:.1f}MB)")
    audio_data = TEST_FILE.read_bytes()

    print("开始识别...")
    text, segments = await engine.transcribe_file(audio_data)

    print(f"\n{'='*60}")
    print(f"识别结果 ({len(segments)} 个片段):")
    print(f"{'='*60}")
    for seg in segments:
        print(f"[{seg.start:.2f}s - {seg.end:.2f}s] {seg.text}")
    print(f"\n{'='*60}")
    print(f"完整文本:\n{text}")


if __name__ == "__main__":
    asyncio.run(test_transcribe())
