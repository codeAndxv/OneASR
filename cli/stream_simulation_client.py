"""流式语音识别模拟客户端。

将本地音视频文件转为音频流，模拟麦克风实时输入，发送到 OneASR 的
OpenAI Realtime Transcription 风格 WebSocket 接口。

支持格式: wav, mp3, flac, aac, ogg, m4a, opus, wma,
          mp4, mkv, avi, mov, flv, webm 等（任何 ffmpeg 支持的格式）。

用法:
    python -m cli.stream_simulation_client <audio_file> [options]

示例:
    # 基本用法（支持 wav/mp3/mp4 等）
    python -m cli.stream_simulation_client test.wav
    python -m cli.stream_simulation_client video.mp4
    python -m cli.stream_simulation_client podcast.mp3

    # 指定语言和引擎
    python -m cli.stream_simulation_client test.wav --language zh --model wlk-live

    # 调整分块大小（模拟不同麦克风采样间隔）
    python -m cli.stream_simulation_client test.wav --chunk-ms 50

    # 10 倍速播放（快速测试长音频）
    python -m cli.stream_simulation_client test.wav --speed 10
"""

import argparse
import asyncio
import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# 清除代理环境变量，避免 SOCKS 代理干扰 localhost 连接
for _var in ("http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
    os.environ.pop(_var, None)


# ── 音频参数 ──────────────────────────────────────────────────────

PCM_SAMPLE_RATE = 16000
PCM_CHANNELS = 1
PCM_SAMPLE_WIDTH = 2  # s16le = 2 bytes per sample

# 支持的文件格式（ffmpeg 支持的所有常见音视频格式）
SUPPORTED_EXTENSIONS = {
    # 音频格式
    ".wav", ".mp3", ".flac", ".aac", ".ogg", ".m4a", ".opus", ".wma", ".alac",
    # 视频格式（提取音频流）
    ".mp4", ".mkv", ".avi", ".mov", ".flv", ".webm", ".ts", ".mts", ".3gp",
}


def check_ffmpeg_available() -> bool:
    """检查 ffmpeg 是否可用。"""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, check=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def convert_to_pcm(input_path: str, sample_rate: int = PCM_SAMPLE_RATE) -> bytes:
    """使用 ffmpeg 将音视频文件转换为 PCM s16le mono。

    Args:
        input_path: 输入文件路径
        sample_rate: 目标采样率

    Returns:
        原始 PCM 数据
    """
    cmd = [
        "ffmpeg",
        "-i", input_path,
        "-vn",  # 去掉视频流
        "-acodec", "pcm_s16le",
        "-ar", str(sample_rate),
        "-ac", str(PCM_CHANNELS),
        "-f", "s16le",
        "-loglevel", "error",
        "pipe:1",
    ]

    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 转换失败: {result.stderr.decode().strip()}")

    return result.stdout


def get_audio_duration(input_path: str) -> float:
    """获取音视频文件的音频时长（秒）。"""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        input_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return 0.0
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def pcm_to_base64(pcm_data: bytes) -> str:
    """将 PCM 数据编码为 base64 字符串。"""
    return base64.b64encode(pcm_data).decode("ascii")


class StreamSimulationClient:
    """流式语音识别模拟客户端。

    读取本地音视频文件，将其转为 PCM 音频流，模拟麦克风实时输入
    发送到 OneASR WebSocket 接口，并实时显示识别结果。
    """

    def __init__(
        self,
        url: str = "ws://127.0.0.1:8020/v1/realtime",
        api_key: str = "oneasr-key",
        language: str | None = None,
        model: str | None = None,
        chunk_ms: int = 100,
        speed: float = 1.0,
    ):
        """
        Args:
            url: WebSocket 服务端地址
            api_key: API Key
            language: 语言代码（如 zh、en、auto）
            model: Provider 名称
            chunk_ms: 每次发送的音频时长（毫秒），模拟麦克风采样间隔
            speed: 播放速度倍率（1.0=实时，2.0=两倍速，10.0=十倍速）
        """
        self.url = url
        self.api_key = api_key
        self.language = language
        self.model = model
        self.chunk_ms = chunk_ms
        self.speed = max(0.1, speed)  # 最低 0.1 倍速

        # 计算每个 chunk 的字节数
        self.chunk_bytes = int(
            PCM_SAMPLE_RATE * PCM_CHANNELS * PCM_SAMPLE_WIDTH * chunk_ms / 1000
        )
        # 每个 chunk 的实际时长（秒）
        self.chunk_duration = chunk_ms / 1000.0

    async def run(self, file_path: str):
        """执行流式转录。

        Args:
            file_path: 本地音视频文件路径
        """
        path = Path(file_path)
        if not path.exists():
            print(f"错误: 文件不存在: {file_path}")
            sys.exit(1)

        # 检查 ffmpeg
        if not check_ffmpeg_available():
            print("错误: 未找到 ffmpeg，请先安装: brew install ffmpeg / apt install ffmpeg")
            sys.exit(1)

        # 检查文件格式
        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            print(f"警告: 文件格式 '{ext}' 可能不被支持，尝试继续...")
            print(f"支持的格式: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")

        # 获取文件信息
        duration = get_audio_duration(str(path))
        file_size_mb = path.stat().st_size / (1024 * 1024)
        print(f"文件: {path.name} ({file_size_mb:.1f} MB, {duration:.1f}s)")

        # 转换为 PCM
        print(f"转换为 PCM {PCM_SAMPLE_RATE}Hz mono s16le...")
        pcm_data = convert_to_pcm(str(path))
        pcm_duration = len(pcm_data) / (PCM_SAMPLE_RATE * PCM_CHANNELS * PCM_SAMPLE_WIDTH)
        print(f"PCM 数据: {len(pcm_data)} bytes, {pcm_duration:.1f}s")

        # 计算分块信息
        total_chunks = (len(pcm_data) + self.chunk_bytes - 1) // self.chunk_bytes
        estimated_time = pcm_duration / self.speed
        print(f"分块: {total_chunks} chunks × {self.chunk_ms}ms, "
              f"预计耗时 {estimated_time:.1f}s (速度 {self.speed}x)")
        print(f"连接: {self.url}")
        print("─" * 60)

        try:
            import websockets
        except ImportError:
            print("错误: 需要安装 websockets 库: pip install websockets")
            sys.exit(1)

        async with websockets.connect(
            self.url,
            additional_headers={"X-API-Key": self.api_key} if self.api_key else {},
            max_size=10 * 1024 * 1024,
            proxy=None,
        ) as ws:
            print("已连接到服务端")

            # 1. 发送 session.update
            session_update = {
                "type": "session.update",
                "session": {
                    "type": "transcription",
                    "audio": {
                        "input": {
                            "format": {
                                "type": "audio/pcm",
                                "rate": PCM_SAMPLE_RATE,
                            },
                            "transcription": {
                                "model": self.model or "whisperlivekit",
                            },
                        },
                    },
                },
            }
            if self.language:
                session_update["session"]["audio"]["input"]["transcription"]["language"] = self.language

            await ws.send(json.dumps(session_update))
            print(f"已发送 session.update (language={self.language}, model={self.model})")

            # 等待 session.updated
            response = await ws.recv()
            resp_data = json.loads(response)
            if resp_data.get("type") == "session.updated":
                print("会话已配置，开始发送音频...")
            elif resp_data.get("type") == "error":
                print(f"错误: {resp_data.get('error', {}).get('message', '未知错误')}")
                return
            else:
                print(f"意外响应: {resp_data.get('type')}")
                return

            print("─" * 60)

            # 2. 启动结果接收任务
            received_events = []

            async def receive_results():
                try:
                    async for msg in ws:
                        event = json.loads(msg)
                        event_type = event.get("type")

                        if event_type == "conversation.item.input_audio_transcription.delta":
                            delta = event.get("delta", "")
                            # 用 \r + \n 确保不被进度条覆盖
                            print(f"\r\033[K[delta] {delta}")

                        elif event_type == "conversation.item.input_audio_transcription.completed":
                            transcript = event.get("transcript", "")
                            print(f"\033[K[完成] {transcript}")
                            received_events.append(event)

                        elif event_type == "done":
                            print("\n[完成] 服务端已结束转录")
                            return

                        elif event_type == "heartbeat":
                            pass  # 忽略心跳

                        elif event_type == "error":
                            error = event.get("error", {})
                            print(f"\n[错误] {error.get('code', '')}: {error.get('message', '')}")

                        elif event_type == "session.updated":
                            pass

                except websockets.exceptions.ConnectionClosed:
                    pass
                except Exception as e:
                    print(f"\n接收结果异常: {e}")

            receive_task = asyncio.create_task(receive_results())

            # 3. 逐块发送音频
            t_start = time.time()
            sent_bytes = 0
            chunk_index = 0

            for i in range(0, len(pcm_data), self.chunk_bytes):
                chunk = pcm_data[i:i + self.chunk_bytes]
                chunk_b64 = pcm_to_base64(chunk)

                await ws.send(json.dumps({
                    "type": "input_audio_buffer.append",
                    "audio": chunk_b64,
                }))

                sent_bytes += len(chunk)
                chunk_index += 1
                progress = sent_bytes / len(pcm_data) * 100

                # 进度显示
                elapsed = time.time() - t_start
                sent_duration = sent_bytes / (PCM_SAMPLE_RATE * PCM_CHANNELS * PCM_SAMPLE_WIDTH)
                print(
                    f"\r[发送] {progress:5.1f}% | "
                    f"{sent_duration:.1f}s / {pcm_duration:.1f}s | "
                    f"已用 {elapsed:.1f}s",
                    end="",
                    flush=True,
                )

                # 模拟实时发送间隔
                if self.speed > 0:
                    sleep_time = self.chunk_duration / self.speed
                    await asyncio.sleep(sleep_time)

            print(f"\n音频发送完成 ({sent_bytes} bytes)")

            # 4. 发送 commit 信号
            await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
            print("已发送 commit，等待最终结果...")

            # 5. 等待接收完成（服务端会在结果发送完毕后关闭连接）
            try:
                await receive_task
            except asyncio.CancelledError:
                pass

            # 统计
            elapsed = time.time() - t_start
            print("─" * 60)
            print(f"完成! 收到 {len(received_events)} 条转录结果, 耗时 {elapsed:.1f}s")


def main():
    parser = argparse.ArgumentParser(
        description="流式语音识别模拟客户端 — 将本地音视频文件模拟为麦克风实时输入",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s test.wav                          # WAV 音频
  %(prog)s video.mp4                         # MP4 视频（自动提取音频）
  %(prog)s podcast.mp3                       # MP3 音频
  %(prog)s movie.mkv --language zh           # MKV 视频，指定中文
  %(prog)s test.wav --speed 10               # 10倍速快速测试
  %(prog)s test.wav --chunk-ms 50            # 50ms 分块（更细粒度）
  %(prog)s test.wav --url ws://remote:8020/v1/realtime  # 远程服务
        """,
    )
    parser.add_argument("file", help="音视频文件路径 (支持 wav/mp3/mp4/mkv/avi/mov/flac/ogg 等)")
    parser.add_argument(
        "--url",
        default="ws://127.0.0.1:8020/v1/realtime",
        help="WebSocket 服务端地址 (默认: ws://127.0.0.1:8020/v1/realtime)",
    )
    parser.add_argument(
        "--api-key",
        default="oneasr-key",
        help="API Key (默认: oneasr-key)",
    )
    parser.add_argument(
        "--language", "-l",
        default=None,
        help="语言代码 (如 zh, en, auto)",
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="Provider 名称 (如 wlk-live)",
    )
    parser.add_argument(
        "--chunk-ms",
        type=int,
        default=100,
        help="每次发送的音频时长，毫秒 (默认: 100)",
    )
    parser.add_argument(
        "--speed", "-s",
        type=float,
        default=1.0,
        help="播放速度倍率 (默认: 1.0, 即实时)",
    )

    args = parser.parse_args()

    client = StreamSimulationClient(
        url=args.url,
        api_key=args.api_key,
        language=args.language,
        model=args.model,
        chunk_ms=args.chunk_ms,
        speed=args.speed,
    )

    asyncio.run(client.run(args.file))


if __name__ == "__main__":
    main()
