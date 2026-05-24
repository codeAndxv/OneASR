"""测试 FireRedASR 引擎文件识别功能。"""

import asyncio
from pathlib import Path

from app.core.config import app_config
from app.engines.firered_engine import FireRedEngine
from app.utils.format import format_output

TEST_FILE = Path("/Volumes/µ/files/DuRT/DuRT-增加文本校正功能.mp4")


async def test_transcribe():
    if not TEST_FILE.exists():
        print(f"测试文件不存在: {TEST_FILE}")
        return

    print("加载 FireRedASR 模型...")
    config = app_config.get_engine_config("firered")
    engine = FireRedEngine(config)

    print(f"读取文件: {TEST_FILE.name} ({TEST_FILE.stat().st_size / 1024 / 1024:.1f}MB)")
    audio_data = TEST_FILE.read_bytes()

    print("开始识别...")
    text, segments = await engine.transcribe_file(audio_data)

    print(f"\n{'='*60}")
    print(f"识别结果 ({len(segments)} 个片段):")
    print(f"{'='*60}")
    for seg in segments:
        if seg.start == 0 and seg.end == 0:
            print(f"{seg.text}")
        else:
            print(f"[{seg.start:.2f}s - {seg.end:.2f}s] {seg.text}")

    print(f"\n{'='*60}")
    print(f"完整文本:\n{text}")

    # 输出 SRT 格式
    print(f"\n{'='*60}")
    print("SRT 格式:")
    print(f"{'='*60}")
    srt_content = format_output(text, segments, "srt")
    print(srt_content)

    # 保存 SRT 文件
    srt_path = TEST_FILE.with_suffix(".srt")
    srt_path.write_text(srt_content, encoding="utf-8")
    print(f"\nSRT 文件已保存: {srt_path}")


if __name__ == "__main__":
    asyncio.run(test_transcribe())
