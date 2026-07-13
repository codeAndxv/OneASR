"""实时语音识别集成测试。

将本地视频文件通过 WebSocket 流式发送到 /ws/transcribe/stream，
验证 WhisperLiveKit 实时识别功能并展示结果。

用法:
    python -m tests.test_stream_integration
    python -m tests.test_stream_integration /path/to/audio.mp3 --language zh
"""

import asyncio
import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# 禁用代理以确保 localhost 连接正常
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ.pop("all_proxy", None)
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("ALL_PROXY", None)

import websockets

from app.utils.stream import convert_to_pcm, get_audio_duration

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_VIDEO = "/Users/dudu/Files/Video/37047240970-1-192.mp4"


async def test_stream(
    file_path: str,
    host: str = "localhost",
    port: int = 8020,
    language: str = "zh",
    chunk_duration: float = 1.0,
):
    """执行实时流式识别测试。

    Args:
        file_path: 音视频文件路径
        host: 服务地址
        port: 服务端口
        language: 语言代码
        chunk_duration: 每块音频时长（秒）
    """
    file_path = Path(file_path)
    if not file_path.exists():
        logger.error("文件不存在: %s", file_path)
        sys.exit(1)

    # 1. 转换音频
    logger.info("=" * 60)
    logger.info("实时语音识别集成测试")
    logger.info("=" * 60)
    logger.info("文件: %s", file_path.name)
    logger.info("语言: %s", language)
    logger.info("块大小: %.1f 秒", chunk_duration)

    logger.info("正在转换音频...")
    pcm_data = convert_to_pcm(file_path)
    duration = get_audio_duration(pcm_data)
    logger.info("音频时长: %.1f 秒, 数据大小: %.2f MB", duration, len(pcm_data) / 1024 / 1024)

    # 2. 连接 WebSocket
    uri = f"ws://{host}:{port}/ws/transcribe/stream?engine=wlk&language={language}"
    logger.info("连接: %s", uri)

    all_lines = []
    buffer_text = ""
    response_count = 0
    error_msg = None
    chunk_count = 0
    elapsed = 0.0

    try:
        async with websockets.connect(uri, proxy=None, open_timeout=30) as ws:
            # 读取 config 消息（模型加载可能需要时间）
            config_raw = await asyncio.wait_for(ws.recv(), timeout=120.0)
            config_msg = json.loads(config_raw)
            logger.info("收到配置: %s", config_msg)

            if config_msg.get("type") == "error":
                logger.error("服务返回错误: %s", config_msg.get("error"))
                return

            # 启动接收任务
            async def receive_results():
                nonlocal all_lines, buffer_text, response_count, error_msg
                try:
                    while True:
                        raw = await asyncio.wait_for(ws.recv(), timeout=600.0)
                        data = json.loads(raw)

                        if data.get("type") == "ready_to_stop":
                            logger.info("收到完成信号")
                            break

                        response_count += 1
                        status = data.get("status", "")

                        if status == "error":
                            error_msg = data.get("error", "未知错误")
                            logger.error("识别错误: %s", error_msg)
                            break

                        lines = data.get("lines", [])
                        buffer_text = data.get("buffer_transcription", "")

                        if lines:
                            all_lines = lines

                        # 实时打印进度
                        if response_count % 3 == 0 or lines:
                            confirmed_text = " ".join(l.get("text", "") for l in all_lines)
                            display = confirmed_text[-80:] if len(confirmed_text) > 80 else confirmed_text
                            sys.stdout.write(f"\r  [{response_count}] [{status}] {display}{' ' * 10}")
                            sys.stdout.flush()

                except asyncio.TimeoutError:
                    logger.warning("接收超时")
                except Exception as e:
                    logger.error("接收异常: %s", e)

            recv_task = asyncio.create_task(receive_results())

            # 3. 按实时速度发送 PCM 块
            logger.info("开始发送音频...")
            start_time = time.time()
            chunk_size = int(16000 * 2 * chunk_duration)

            for i in range(0, len(pcm_data), chunk_size):
                chunk = pcm_data[i : i + chunk_size]
                await ws.send(chunk)
                chunk_count += 1
                await asyncio.sleep(chunk_duration)

            # 发送结束信号
            logger.info("\n音频发送完成，发送结束信号...")
            await ws.send(b"")

            # 等待接收完成
            await asyncio.wait_for(recv_task, timeout=600.0)
            elapsed = time.time() - start_time

    except websockets.exceptions.ConnectionClosed as e:
        logger.error("WebSocket 连接关闭: %s", e)
    except ConnectionRefusedError:
        logger.error("无法连接到 %s:%d，请确认服务已启动", host, port)
        sys.exit(1)
    except Exception as e:
        logger.error("测试异常: %s", e, exc_info=True)

    # 4. 展示结果
    print("\n")
    print("=" * 60)
    print("识别结果")
    print("=" * 60)

    if error_msg:
        print(f"错误: {error_msg}")
        return

    print(f"响应次数: {response_count}")
    print(f"已确认行数: {len(all_lines)}")
    print(f"发送块数: {chunk_count}")
    print(f"音频时长: {duration:.1f} 秒")
    print(f"处理耗时: {elapsed:.1f} 秒")
    print(f"实时倍率: {elapsed / duration:.2f}x")
    print()

    if all_lines:
        print("已确认文本:")
        print("-" * 60)
        for i, line in enumerate(all_lines, 1):
            speaker = line.get("speaker", "?")
            text = line.get("text", "")
            start = line.get("start", "")
            end = line.get("end", "")
            print(f"  [{start} → {end}] (说话人{speaker}) {text}")

    if buffer_text:
        print(f"\n未确认缓冲: {buffer_text}")

    full_text = " ".join(l.get("text", "") for l in all_lines)
    if buffer_text:
        full_text += " " + buffer_text

    print()
    print("=" * 60)
    print("完整识别文本:")
    print("-" * 60)
    print(full_text.strip())
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="实时语音识别集成测试")
    parser.add_argument("file", nargs="?", default=DEFAULT_VIDEO, help="音视频文件路径")
    parser.add_argument("--host", default="localhost", help="服务地址")
    parser.add_argument("--port", type=int, default=8020, help="服务端口")
    parser.add_argument("--language", default="zh", help="语言代码")
    parser.add_argument("--chunk", type=float, default=1.0, help="每块音频时长（秒）")
    args = parser.parse_args()

    asyncio.run(test_stream(
        file_path=args.file,
        host=args.host,
        port=args.port,
        language=args.language,
        chunk_duration=args.chunk,
    ))


if __name__ == "__main__":
    main()
