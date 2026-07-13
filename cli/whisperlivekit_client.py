"""WhisperLiveKit API 客户端，封装 REST 文件转录和 WebSocket 流式转录。"""

import asyncio
import json
import logging
import struct
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Callable

import httpx
import websockets
import websockets.asyncio.client

logger = logging.getLogger(__name__)


# ============================================================
# Data Classes
# ============================================================

@dataclass
class Segment:
    """转录片段。"""
    id: int
    start: float
    end: float
    text: str


@dataclass
class TranscriptionResult:
    """文件转录结果。"""
    text: str
    segments: list[Segment] = field(default_factory=list)
    language: str = ""
    duration: float = 0.0


@dataclass
class StreamSegment:
    """流式转录片段。"""
    text: str
    start: str
    end: str
    speaker: int = 1
    detected_language: str = ""


@dataclass
class StreamState:
    """流式转录状态。"""
    status: str = ""
    lines: list[StreamSegment] = field(default_factory=list)
    buffer_transcription: str = ""
    remaining_time: float = 0.0


# ============================================================
# REST API Client
# ============================================================

class WLKRestClient:
    """WhisperLiveKit REST API 客户端。

    用于文件转录，接口兼容 OpenAI Audio Transcriptions API。

    使用示例:
        client = WLKRestClient("http://localhost:8020")
        result = client.transcribe_file("audio.wav")
        print(result.text)

        # 异步版本
        result = await client.transcribe_file_async("audio.wav")
    """

    def __init__(self, base_url: str, timeout: float = 300):
        """
        Args:
            base_url: 服务器地址，如 "http://localhost:8020"
            timeout: 请求超时时间（秒），默认 300 秒
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # --- Health ---

    def health(self) -> dict:
        """检查服务器健康状态。"""
        resp = httpx.get(f"{self.base_url}/health", timeout=5)
        resp.raise_for_status()
        return resp.json()

    async def health_async(self) -> dict:
        """异步检查服务器健康状态。"""
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{self.base_url}/health")
            resp.raise_for_status()
            return resp.json()

    # --- Models ---

    def list_models(self) -> list[dict]:
        """获取已加载的模型列表。"""
        resp = httpx.get(f"{self.base_url}/v1/models", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])

    async def list_models_async(self) -> list[dict]:
        """异步获取已加载的模型列表。"""
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{self.base_url}/v1/models")
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])

    # --- File Transcription ---

    def transcribe_file(
        self,
        file_path: str | Path,
        language: str = "",
        response_format: str = "verbose_json",
    ) -> TranscriptionResult:
        """转录音频/视频文件。

        Args:
            file_path: 文件路径（支持任何 ffmpeg 可解码的格式）
            language: ISO 639-1 语言代码，空字符串表示自动检测
            response_format: 响应格式，可选 json/verbose_json/text/srt/vtt

        Returns:
            转录结果
        """
        file_path = Path(file_path)
        with open(file_path, "rb") as f:
            return self._transcribe(
                file_data=f.read(),
                file_name=file_path.name,
                language=language,
                response_format=response_format,
            )

    async def transcribe_file_async(
        self,
        file_path: str | Path,
        language: str = "",
        response_format: str = "verbose_json",
    ) -> TranscriptionResult:
        """异步转录音频/视频文件。"""
        file_path = Path(file_path)
        file_data = file_path.read_bytes()
        return await self._transcribe_async(
            file_data=file_data,
            file_name=file_path.name,
            language=language,
            response_format=response_format,
        )

    def transcribe_audio_data(
        self,
        audio_data: bytes,
        file_name: str = "audio.wav",
        language: str = "",
        response_format: str = "verbose_json",
    ) -> TranscriptionResult:
        """转录音频数据。

        Args:
            audio_data: 音频文件的二进制数据
            file_name: 文件名（用于确定 Content-Type）
            language: ISO 639-1 语言代码
            response_format: 响应格式

        Returns:
            转录结果
        """
        return self._transcribe(
            file_data=audio_data,
            file_name=file_name,
            language=language,
            response_format=response_format,
        )

    # --- Internal ---

    def _content_type(self, file_name: str) -> str:
        ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "wav"
        types = {
            "wav": "audio/wav", "mp3": "audio/mpeg", "m4a": "audio/mp4",
            "flac": "audio/flac", "ogg": "audio/ogg", "aac": "audio/aac",
        }
        return types.get(ext, f"audio/{ext}")

    def _transcribe(
        self,
        file_data: bytes,
        file_name: str,
        language: str,
        response_format: str,
    ) -> TranscriptionResult:
        boundary = "----WLKBoundary"
        body = self._build_multipart(file_data, file_name, language, response_format, boundary)

        resp = httpx.post(
            f"{self.base_url}/v1/audio/transcriptions",
            content=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        if response_format in ("json", "verbose_json"):
            return self._parse_response(resp.json(), response_format)
        # srt, vtt, text 等格式返回纯文本
        return TranscriptionResult(text=resp.text)

    async def _transcribe_async(
        self,
        file_data: bytes,
        file_name: str,
        language: str,
        response_format: str,
    ) -> TranscriptionResult:
        boundary = "----WLKBoundary"
        body = self._build_multipart(file_data, file_name, language, response_format, boundary)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/v1/audio/transcriptions",
                content=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            )
            resp.raise_for_status()
            if response_format in ("json", "verbose_json"):
                return self._parse_response(resp.json(), response_format)
            return TranscriptionResult(text=resp.text)

    def _build_multipart(
        self,
        file_data: bytes,
        file_name: str,
        language: str,
        response_format: str,
        boundary: str,
    ) -> bytes:
        parts = []
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n'.encode())
        parts.append(f"Content-Type: {self._content_type(file_name)}\r\n\r\n".encode())
        parts.append(file_data)
        parts.append(b"\r\n")

        parts.append(f"--{boundary}\r\n".encode())
        parts.append(b'Content-Disposition: form-data; name="model"\r\n\r\n')
        parts.append(b"whisper\r\n")

        parts.append(f"--{boundary}\r\n".encode())
        parts.append(b'Content-Disposition: form-data; name="response_format"\r\n\r\n')
        parts.append(f"{response_format}\r\n".encode())

        if language and language.lower() != "auto":
            parts.append(f"--{boundary}\r\n".encode())
            parts.append(b'Content-Disposition: form-data; name="language"\r\n\r\n')
            parts.append(f"{language}\r\n".encode())

        parts.append(f"--{boundary}--\r\n".encode())
        return b"".join(parts)

    def _parse_response(self, json_data: dict, response_format: str) -> TranscriptionResult:
        if response_format in ("json", "verbose_json"):
            segments = [
                Segment(
                    id=s.get("id", 0),
                    start=s.get("start", 0.0),
                    end=s.get("end", 0.0),
                    text=s.get("text", ""),
                )
                for s in json_data.get("segments", [])
            ]
            return TranscriptionResult(
                text=json_data.get("text", ""),
                segments=segments,
                language=json_data.get("language", ""),
                duration=json_data.get("duration", 0.0),
            )
        return TranscriptionResult(text=json.dumps(json_data, ensure_ascii=False))


# ============================================================
# WebSocket Streaming Client
# ============================================================

class WLKStreamClient:
    """WhisperLiveKit WebSocket 流式转录客户端。

    使用示例:
        client = WLKStreamClient("ws://localhost:8020")

        # 逐块发送音频，收集结果
        async for state in client.stream_file("audio.wav"):
            print(f"[{state.status}] lines={len(state.lines)}")

        # 使用回调
        async def on_result(state: StreamState):
            for line in state.lines:
                print(line.text)

        await client.stream_file("audio.wav", on_result=on_result)
    """

    def __init__(self, base_url: str):
        """
        Args:
            base_url: WebSocket 服务器地址，如 "ws://localhost:8020"
        """
        self.base_url = base_url.rstrip("/")

    def _ws_url(self, language: str = "", mode: str = "full") -> str:
        host = self.base_url
        if host.startswith("http://"):
            host = "ws://" + host[7:]
        elif host.startswith("https://"):
            host = "wss://" + host[8:]
        elif not host.startswith("ws://") and not host.startswith("wss://"):
            host = "ws://" + host

        params = []
        if language and language.lower() != "auto":
            params.append(f"language={language}")
        if mode != "full":
            params.append(f"mode={mode}")

        query = ("?" + "&".join(params)) if params else ""
        return f"{host}/asr{query}"

    async def connect(
        self,
        language: str = "",
        mode: str = "full",
    ) -> websockets.asyncio.client.ClientConnection:
        """建立 WebSocket 连接。

        Args:
            language: ISO 639-1 语言代码
            mode: 输出模式 ("full" 或 "diff")

        Returns:
            WebSocket 连接对象
        """
        url = self._ws_url(language, mode)
        logger.info("Connecting to %s", url)
        ws = await websockets.asyncio.client.connect(url)
        # 接收 config 消息
        config_msg = await asyncio.wait_for(ws.recv(), timeout=5)
        config = json.loads(config_msg)
        logger.info("Config: useAudioWorklet=%s, mode=%s", config.get("useAudioWorklet"), config.get("mode"))
        return ws

    async def stream_audio(
        self,
        ws: websockets.asyncio.client.ClientConnection,
        audio_chunks: list[bytes],
        use_audio_worklet: bool = True,
    ) -> AsyncIterator[StreamState]:
        """发送音频块并接收转录结果。

        Args:
            ws: WebSocket 连接
            audio_chunks: 音频数据块列表
            use_audio_worklet: 是否使用 PCM 格式（True=s16le, False=编码音频）

        Yields:
            每次收到更新时的完整状态
        """
        for chunk in audio_chunks:
            await ws.send(chunk)

        # 发送结束信号
        await ws.send(b"")

        # 接收结果
        lines: list[StreamSegment] = []
        async for msg in ws:
            if isinstance(msg, bytes):
                continue
            data = json.loads(msg)
            msg_type = data.get("type", "")

            if msg_type == "ready_to_stop":
                return

            if msg_type in ("snapshot", "diff") and "lines" in data:
                lines = self._reconstruct_lines(lines, data)

            state = StreamState(
                status=data.get("status", ""),
                lines=list(lines),
                buffer_transcription=data.get("buffer_transcription", ""),
                remaining_time=data.get("remaining_time_transcription", 0.0),
            )
            yield state

    def _reconstruct_lines(self, current: list[StreamSegment], msg: dict) -> list[StreamSegment]:
        """应用 diff 或 snapshot 到当前 lines 列表。"""
        if msg.get("type") == "snapshot":
            return [self._parse_line(l) for l in msg.get("lines", [])]

        # diff
        n_pruned = msg.get("lines_pruned", 0)
        if n_pruned > 0:
            current = current[n_pruned:]
        for new_line in msg.get("new_lines", []):
            current.append(self._parse_line(new_line))
        return current

    @staticmethod
    def _parse_line(raw: dict) -> StreamSegment:
        return StreamSegment(
            text=raw.get("text", "") or "",
            start=raw.get("start", "0:00:00"),
            end=raw.get("end", "0:00:00"),
            speaker=raw.get("speaker", 1),
            detected_language=raw.get("detected_language", ""),
        )

    # --- High-level: Stream file ---

    async def stream_file(
        self,
        file_path: str | Path,
        language: str = "",
        chunk_duration: float = 0.5,
        sample_rate: int = 16000,
        on_result: Callable[[StreamState], None] | None = None,
    ) -> StreamState:
        """流式转录文件（模拟实时输入）。

        读取音频文件，分块发送到 WebSocket，收集最终结果。

        当服务器 useAudioWorklet=true 时，发送原始 PCM s16le 数据；
        当 useAudioWorklet=false 时，发送编码音频数据（WAV 等），由服务器 FFmpeg 解码。

        Args:
            file_path: 音频文件路径
            language: 语言代码
            chunk_duration: 每块时长（秒），默认 0.5 秒
            sample_rate: 采样率（仅 PCM 模式使用），默认 16000
            on_result: 可选的回调函数，每次收到更新时调用

        Returns:
            最终的转录状态
        """
        file_path = Path(file_path)
        ws = await self.connect(language=language)
        last_state = StreamState()

        try:
            # 重新连接以获取 config（connect 已经读取了 config，这里直接发送音频）
            # connect 内部已经消费了 config 消息
            raw_data = file_path.read_bytes()
            chunk_size = max(1, len(raw_data) // 10)  # 分成 ~10 块
            chunks = [raw_data[i:i + chunk_size] for i in range(0, len(raw_data), chunk_size)]

            for chunk in chunks:
                await ws.send(chunk)
            await ws.send(b"")  # 结束信号

            # 接收结果
            lines: list[StreamSegment] = []
            async for msg in ws:
                if isinstance(msg, bytes):
                    continue
                data = json.loads(msg)
                msg_type = data.get("type", "")

                if msg_type == "ready_to_stop":
                    break

                if "lines" in data:
                    lines = self._apply_update(lines, data)

                last_state = StreamState(
                    status=data.get("status", ""),
                    lines=list(lines),
                    buffer_transcription=data.get("buffer_transcription", ""),
                    remaining_time=data.get("remaining_time_transcription", 0.0),
                )
                if on_result:
                    on_result(last_state)
        finally:
            await ws.close()

        return last_state

    @staticmethod
    def _apply_update(lines: list[StreamSegment], data: dict) -> list[StreamSegment]:
        """应用 snapshot 或 diff 更新到 lines 列表。"""
        msg_type = data.get("type", "")
        if "lines" in data and not msg_type:
            # full mode (no type field)
            return [WLKStreamClient._parse_line(l) for l in data.get("lines", [])]
        if msg_type == "snapshot":
            return [WLKStreamClient._parse_line(l) for l in data.get("lines", [])]

        # diff
        n_pruned = data.get("lines_pruned", 0)
        if n_pruned > 0:
            lines = lines[n_pruned:]
        for new_line in data.get("new_lines", []):
            lines.append(WLKStreamClient._parse_line(new_line))
        return lines


# ============================================================
# Combined Client
# ============================================================

class WLKClient:
    """WhisperLiveKit 统一客户端，同时支持 REST 和 WebSocket。

    使用示例:
        client = WLKClient("http://localhost:8020")

        # 文件转录
        result = client.rest.transcribe_file("audio.wav")
        print(result.text)

        # 流式转录
        last = await client.stream.stream_file("audio.wav")
        for line in last.lines:
            print(line.text)
    """

    def __init__(self, base_url: str, timeout: float = 300):
        self.rest = WLKRestClient(base_url, timeout=timeout)

        ws_url = base_url
        if ws_url.startswith("http://"):
            ws_url = "ws://" + ws_url[7:]
        elif ws_url.startswith("https://"):
            ws_url = "wss://" + ws_url[8:]
        self.stream = WLKStreamClient(ws_url)

    def health(self) -> dict:
        return self.rest.health()

    async def health_async(self) -> dict:
        return await self.rest.health_async()


# ============================================================
# Deepgram SDK Client
# ============================================================

class WLKDeepgramClient:
    """使用 Deepgram Python SDK 连接 WhisperLiveKit 的 /v1/listen WebSocket 接口。

    WhisperLiveKit 的 /v1/listen 兼容 Deepgram 的 Live Transcription WebSocket 协议。
    本客户端通过自定义 DeepgramClientEnvironment 将 SDK 指向本地服务器。

    使用示例:
        client = WLKDeepgramClient("http://localhost:8020")
        result = client.transcribe_file("audio.wav", language="en")
        print(result)
    """

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        ws_url = self.base_url
        if ws_url.startswith("http://"):
            ws_url = "ws://" + ws_url[7:]
        elif ws_url.startswith("https://"):
            ws_url = "wss://" + ws_url[8:]
        elif not ws_url.startswith("ws://") and not ws_url.startswith("wss://"):
            ws_url = "ws://" + ws_url
        self.ws_url = ws_url

    def _create_client(self):
        """创建指向本地服务器的 DeepgramClient。"""
        from deepgram import DeepgramClient, DeepgramClientEnvironment

        env = DeepgramClientEnvironment(
            base=self.base_url,
            production=self.ws_url,
            agent=self.ws_url,
            agent_rest=self.base_url,
        )
        return DeepgramClient(api_key="unused", environment=env)

    def transcribe_file(
        self,
        file_path: str | Path,
        language: str = "",
        model: str = "nova-2",
        interim_results: bool = True,
        punctuate: bool = True,
    ) -> str:
        """使用 Deepgram SDK 流式转录音频文件。

        Args:
            file_path: 音频文件路径（WAV 格式，16kHz 单声道最佳）
            language: 语言代码（如 "en", "zh"），空字符串表示自动检测
            model: Deepgram 模型名称
            interim_results: 是否返回中间结果
            punctuate: 是否自动加标点

        Returns:
            转录文本
        """
        file_path = Path(file_path)

        with wave.open(str(file_path), "rb") as wf:
            sr = wf.getframerate()
            ch = wf.getnchannels()
            raw = wf.readframes(wf.getnframes())

        logger.info("Audio: %dHz, %dch, %d bytes", sr, ch, len(raw))

        client = self._create_client()

        # 构建连接参数
        connect_kwargs = {
            "model": model,
            "encoding": "linear16",
            "sample_rate": sr,
            "channels": ch,
            "interim_results": interim_results,
            "punctuate": punctuate,
        }
        if language and language.lower() != "auto":
            connect_kwargs["language"] = language

        print(f"Connecting to {self.ws_url}/v1/listen ...")
        with client.listen.v1.connect(**connect_kwargs) as socket:
            print("Connected!")

            # 分块发送音频（每块 0.5 秒）
            chunk_size = sr * 2 * ch // 2  # 0.5 second
            chunks = [raw[i:i+chunk_size] for i in range(0, len(raw), chunk_size)]
            total = len(chunks)

            for i, chunk in enumerate(chunks):
                socket.send_media(chunk)
                if (i + 1) % 20 == 0 or i + 1 == total:
                    pct = (i + 1) / total * 100
                    print(f"\r  Sending: {pct:.0f}% ({i+1}/{total})", end="", flush=True)

            print("\n  Audio sent.")

            # 发送结束信号
            socket.send_finalize()
            print("  Finalize sent.\n")

            # 接收结果
            results = []
            import time
            start = time.time()
            timeout = 60

            while time.time() - start < timeout:
                try:
                    msg = next(iter(socket))
                    if hasattr(msg, "type"):
                        if msg.type == "Results":
                            alt = msg.channel.alternatives[0]
                            transcript = alt.transcript
                            if transcript:
                                is_final = getattr(msg, "is_final", True)
                                if is_final:
                                    results.append(transcript)
                                    print(f"\033[32m✓\033[0m {transcript}")
                                else:
                                    sys.stdout.write(f"\r\033[33m...\033[0m {transcript}\033[K")
                                    sys.stdout.flush()
                        elif msg.type == "Metadata":
                            dur = getattr(msg, "duration", 0)
                            print(f"  Metadata: duration={dur}s")
                except StopIteration:
                    break
                except Exception as e:
                    logger.debug("Receive error: %s", e)
                    break

            print()
            return " ".join(results)


# CLI
# ============================================================
def _get_arg(name: str, default: str | None = None) -> str | None:
    """从 sys.argv 中按名称获取参数值，支持 --name=value 和 --name value 两种形式。"""
    for arg in sys.argv[1:]:
        if arg.startswith(f"{name}="):
            return arg.split("=", 1)[1]
    if name in sys.argv:
        idx = sys.argv.index(name)
        return sys.argv[idx + 1] if idx + 1 < len(sys.argv) else default
    return default


def _format_srt_time(seconds: float) -> str:
    """将秒数转为 SRT 时间格式 HH:MM:SS,mmm。"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("用法: python whisperlivekit_client.py <server_url> <file_path> [options]")
        print("选项:")
        print("  --mode ws|rest|deepgram   转录方式 (默认 ws)")
        print("  --language <lang>         语言代码，如 en/zh (默认 auto)")
        print("  --chunk-duration <sec>    每次发送的音频时长秒数 (默认 0.5)")
        print("  --format <fmt>            REST 模式: verbose_json|srt|vtt|text (默认 verbose_json)")
        print("示例:")
        print("  python whisperlivekit_client.py http://localhost:8020 audio.wav")
        print("  python whisperlivekit_client.py http://localhost:8020 audio.wav --mode deepgram")
        print("  python whisperlivekit_client.py http://localhost:8020 audio.wav --mode rest --format srt")
        sys.exit(1)

    url = sys.argv[1]
    file_path = sys.argv[2]
    mode = _get_arg("--mode", "ws")
    lang = _get_arg("--language", _get_arg("--lang", ""))
    chunk_duration = float(_get_arg("--chunk-duration", "0.5"))

    async def _run_ws():
        """通过 WebSocket 流式发送音频并收集结果。"""
        ws_url = url
        if ws_url.startswith("http://"):
            ws_url = "ws://" + ws_url[7:]
        elif not ws_url.startswith("ws://") and not ws_url.startswith("wss://"):
            ws_url = "ws://" + ws_url

        print(f"WebSocket: {ws_url}/asr")
        print(f"File: {file_path}")
        print(f"Chunk duration: {chunk_duration}s")
        print()

        # 建立连接
        params = []
        if lang and lang.lower() != "auto":
            params.append(f"language={lang}")
        query = ("?" + "&".join(params)) if params else ""
        full_url = f"{ws_url}/asr{query}"

        print(f"Connecting to {full_url} ...")
        ws = await websockets.asyncio.client.connect(full_url)

        # 接收 config
        config_msg = await asyncio.wait_for(ws.recv(), timeout=5)
        config = json.loads(config_msg)
        use_pcm = config.get("useAudioWorklet", True)
        print(f"Config: useAudioWorklet={use_pcm}, mode={config.get('mode')}")
        print()

        # 根据 useAudioWorklet 决定发送格式
        if use_pcm:
            # PCM 模式：读取 WAV 并转为 s16le
            with wave.open(file_path, "rb") as wf:
                sr = wf.getframerate()
                ch = wf.getnchannels()
                sw = wf.getsampwidth()
                raw = wf.readframes(wf.getnframes())
                duration = wf.getnframes() / sr

            print(f"WAV: {sr}Hz, {ch}ch, {sw*8}bit, {duration:.1f}s")

            # 转为单声道 s16le
            if ch == 2 and sw == 2:
                mono = bytearray()
                for i in range(0, len(raw), 4):
                    l = int.from_bytes(raw[i:i+2], "little", signed=True)
                    r = int.from_bytes(raw[i+2:i+4], "little", signed=True)
                    mono += ((l + r) // 2).to_bytes(2, "little", signed=True)
                raw = bytes(mono)
                print(f"Converted to mono: {len(raw)} bytes")

            # 计算分块
            chunk_bytes = int(sr * chunk_duration * 2)  # s16le = 2 bytes/sample
        else:
            # 编码模式：直接读取原始文件（WAV/MP3 等），由服务器 FFmpeg 解码
            raw = Path(file_path).read_bytes()
            duration = 0  # unknown without ffprobe
            print(f"File: {Path(file_path).name} ({len(raw)} bytes)")
            # 大块发送（编码音频不需要细粒度分块）
            chunk_bytes = max(1, len(raw) // max(1, int(duration / chunk_duration)) if duration > 0 else len(raw) // 10)

        chunks = [raw[i:i+chunk_bytes] for i in range(0, len(raw), chunk_bytes)]
        total_chunks = len(chunks)
        print(f"Chunks: {total_chunks} x {chunk_bytes} bytes")
        print()

        # 逐块发送音频
        print("Sending audio chunks ...")
        sent_bytes = 0
        for i, chunk in enumerate(chunks):
            await ws.send(chunk)
            sent_bytes += len(chunk)
            pct = sent_bytes / len(raw) * 100
            print(f"\r  [{i+1}/{total_chunks}] {pct:.0f}% ({sent_bytes}/{len(raw)} bytes)", end="", flush=True)

        # 发送结束信号
        await ws.send(b"")
        print("\n  End-of-audio sent.")
        print()

        # 接收转录结果（流式展示）
        print("Receiving transcription ...\n")
        lines: list[StreamSegment] = []
        committed_texts: list[str] = []
        last_committed_count = 0

        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=60)
                if isinstance(msg, bytes):
                    continue
                data = json.loads(msg)
                msg_type = data.get("type", "")

                if msg_type == "ready_to_stop":
                    # 清除 buffer 行
                    sys.stdout.write("\r\033[K")
                    sys.stdout.flush()
                    break

                # 更新 lines
                if "lines" in data:
                    lines = WLKStreamClient._apply_update(lines, data)

                    # 输出新增的 committed lines
                    for l in lines[last_committed_count:]:
                        if l.speaker != -2 and l.text.strip():
                            committed_texts.append(l.text.strip())
                            # 用绿色输出已确认的文本
                            sys.stdout.write(f"\033[32m✓\033[0m {l.start} -> {l.end}  {l.text.strip()}\n")
                            sys.stdout.flush()
                    last_committed_count = len(lines)

                    # 显示当前 buffer（未确认的实时文本）
                    buffer = data.get("buffer_transcription", "")
                    remaining = data.get("remaining_time_transcription", 0)
                    if buffer:
                        sys.stdout.write(f"\r\033[33m...\033[0m {buffer}\033[K")
                        sys.stdout.flush()
                    else:
                        sys.stdout.write(f"\r\033[90m[{remaining:.1f}s remaining]\033[0m\033[K")
                        sys.stdout.flush()

        except asyncio.TimeoutError:
            sys.stdout.write("\n  [timeout]\n")
            sys.stdout.flush()

        await ws.close()

        # 输出最终结果
        print()
        print("=" * 60)
        if committed_texts:
            print("\n".join(committed_texts))
        else:
            print("(no text)")
        print("=" * 60)
        print(f"Lines: {len(lines)}, Segments: {len(committed_texts)}")

    async def _run_rest():
        """通过 REST API 转录。"""
        fmt = _get_arg("--response-format", _get_arg("--format", "verbose_json"))
        print(f"REST: {url}/v1/audio/transcriptions")
        print(f"File: {file_path} (format={fmt})")
        client = WLKRestClient(url)
        result = client.transcribe_file(file_path, language=lang, response_format=fmt)
        if fmt in ("srt", "vtt"):
            print(result.text)
        else:
            print(f"Text: {result.text[:2000]}")
            print(f"Segments: {len(result.segments)}")
            print(f"Language: {result.language}")
            print(f"Duration: {result.duration:.1f}s")

    def _run_deepgram():
        """通过 Deepgram SDK 连接 /v1/listen WebSocket 接口。"""
        print(f"Deepgram SDK -> {url}/v1/listen")
        print(f"File: {file_path}")
        print(f"Language: {lang or 'auto'}")
        print()
        client = WLKDeepgramClient(url)
        result = client.transcribe_file(file_path, language=lang)
        print()
        print("=" * 60)
        print("RESULT")
        print("=" * 60)
        print(result if result else "(no text)")
        print("=" * 60)

    if mode == "deepgram":
        _run_deepgram()
    elif mode == "rest":
        asyncio.run(_run_rest())
    else:
        asyncio.run(_run_ws())
