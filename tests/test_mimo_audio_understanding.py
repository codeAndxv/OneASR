"""测试小米 MiMo 音频理解功能。"""

import asyncio
import sys
from pathlib import Path

import httpx

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.engines.mimo_engine import MiMoEngine


async def test_audio_url():
    """测试通过 URL 进行音频理解。"""
    audio_url = "https://example-files.cnbj1.mi-fds.com/example-files/audio/audio_example.wav"

    async with httpx.AsyncClient() as client:
        response = await client.get(audio_url)
        audio_data = response.content

    # 从 config.yaml 读取配置
    engine = MiMoEngine()
    text, segments = await engine.transcribe_file(audio_data)

    print("=== 音频识别结果 ===")
    print(f"文本: {text}")
    print(f"分段数: {len(segments)}")
    return text, segments


if __name__ == "__main__":
    asyncio.run(test_audio_url())
