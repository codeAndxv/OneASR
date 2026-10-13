"""端到端 API 真实模型全链路集成测试（基于内置 Public Domain 英文音视频，无任何 Mock）。

测试链路：
1. POST /v1/audio/transcriptions -> 真实 faster-whisper 模型识别内置英文语音与 MP4 视频，校验 JSON / SRT 返回。
2. WS   /v1/realtime             -> 真实 xasr 流式模型识别实时 PCM 语音帧，校验增量与最终事件。

运行方式：
    uv run pytest tests/integration/test_e2e_api.py -v -s
"""

import base64
import io
import pytest

from server.core.config import app_config
from server.utils.audio_converter import AudioConverter

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def test_e2e_audio_transcriptions_real_whisper(
    client, auth_headers: dict, sample_en_wav_bytes: bytes
):
    """通过 HTTP POST /v1/audio/transcriptions 驱动真实 faster-whisper 完成转录。"""
    cfg = app_config.get_provider_config("faster-whisper")
    model_dir = cfg.resolve_path(cfg.model_path) if cfg.model_path else None
    if not model_dir or not model_dir.exists():
        pytest.skip(f"本地 Faster-Whisper 模型不存在: {model_dir}")

    resp = client.post(
        "/v1/audio/transcriptions",
        headers=auth_headers,
        files={"file": ("en_speech_15s.wav", io.BytesIO(sample_en_wav_bytes), "audio/wav")},
        data={
            "model": "faster-whisper",
            "language": "en",
            "response_format": "verbose_json",
        },
    )
    assert resp.status_code == 200, f"真实模型接口调用失败: {resp.text}"
    data = resp.json()
    print(f"\n[E2E /v1/audio/transcriptions] 识别结果: {data.get('text')}")
    assert len(data.get("text", "").strip()) > 0
    assert "library" in data["text"].lower() or "everybody" in data["text"].lower()
    assert "segments" in data and len(data["segments"]) >= 2


def test_e2e_long_audio_srt_transcription(
    client, auth_headers: dict, sample_en_long_audio_bytes: bytes
):
    """通过 HTTP POST /v1/audio/transcriptions 转录 120s (2分钟) 长音频并校验多段 SRT 字幕输出。"""
    cfg = app_config.get_provider_config("faster-whisper")
    model_dir = cfg.resolve_path(cfg.model_path) if cfg.model_path else None
    if not model_dir or not model_dir.exists():
        pytest.skip(f"本地 Faster-Whisper 模型不存在: {model_dir}")

    resp = client.post(
        "/v1/audio/transcriptions",
        headers=auth_headers,
        files={"file": ("en_speech_120s.mp3", io.BytesIO(sample_en_long_audio_bytes), "audio/mpeg")},
        data={
            "model": "faster-whisper",
            "language": "en",
            "response_format": "srt",
        },
    )
    assert resp.status_code == 200, f"120s 长音频 SRT 转录失败: {resp.text}"
    srt_text = resp.text
    assert "-->" in srt_text
    # 2 分钟演讲应至少切分出 10 段以上的时间轴字幕
    assert srt_text.count("-->") >= 10


def test_e2e_realtime_websocket_real_xasr(client, sample_en_wav_bytes: bytes):
    """通过 WebSocket /v1/realtime 驱动真实 xasr 引擎完成流式转录。"""
    cfg = app_config.get_provider_config("xasr")
    tokens_path = cfg.resolve_path(getattr(cfg, "tokens_path", ""))
    if not tokens_path or not tokens_path.exists():
        pytest.skip(f"本地 X-ASR 模型文件不存在: {tokens_path}")

    pcm16_bytes = AudioConverter.decode_to_pcm16_bytes(sample_en_wav_bytes, sample_rate=16000)
    # 末尾追加 1 秒静音以顺利触发端点与尾帧收敛
    pcm16_bytes += b"\x00\x00" * 16000

    deltas = []
    completed_transcripts = []

    with client.websocket_connect("/v1/realtime?api_key=oneasr-key") as ws:
        created = ws.receive_json()
        assert created["type"] == "session.created"

        ws.send_json({
            "type": "session.update",
            "session": {
                "type": "transcription",
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": 16000},
                        "transcription": {"model": "xasr", "language": "en"},
                    },
                },
            },
        })
        updated = ws.receive_json()
        assert updated["type"] == "session.updated"

        # 分块发送音频（每次 320ms = 10240 字节）
        chunk_size = int(16000 * 2 * 0.32)
        for i in range(0, len(pcm16_bytes), chunk_size):
            chunk = pcm16_bytes[i : i + chunk_size]
            ws.send_json({
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(chunk).decode("ascii"),
            })

        ws.send_json({"type": "input_audio_buffer.commit"})

        # 读取服务端推送的所有识别事件直到拿到至少一条 completed
        for _ in range(80):
            msg = ws.receive_json()
            msg_type = msg.get("type", "")
            if msg_type == "conversation.item.input_audio_transcription.delta":
                deltas.append(msg.get("delta", ""))
            elif msg_type == "conversation.item.input_audio_transcription.completed":
                completed_transcripts.append(msg.get("transcript", ""))
                break
            elif msg_type == "error":
                pytest.fail(f"WebSocket 收到错误事件: {msg}")

    full_text = " ".join(completed_transcripts) or "".join(deltas)
    print(f"\n[E2E /v1/realtime WebSocket] 流式识别结果: {full_text}")
    assert len(full_text.strip()) > 0
