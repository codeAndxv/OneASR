"""测试 WhisperLiveKit 流式识别接口。"""

import asyncio
import json
import struct
import tempfile
import wave
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.engines.wlk_engine import WLKEngine

# 测试音频文件路径
TEST_AUDIO_FILE = Path("/Users/dudu/Files/Video/clips/lyj111_part000.mp4")


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def _create_test_wav(duration_sec=1.0, sample_rate=16000):
    """创建一个测试用的 WAV 文件。"""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        with wave.open(tmp.name, "w") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            # 生成静音数据
            num_samples = int(sample_rate * duration_sec)
            wav.writeframes(b"\x00\x00" * num_samples)
        return Path(tmp.name)


def _make_mock_front_data():
    """创建一个模拟的 FrontData 对象。"""
    mock = MagicMock()
    mock.to_dict.return_value = {
        "status": "active_transcription",
        "lines": [
            {"speaker": 1, "text": "你好世界", "start": "0:00:01.00", "end": "0:00:03.00"},
        ],
        "buffer_transcription": "测试",
        "buffer_diarization": "",
        "buffer_translation": "",
        "remaining_time_transcription": 0.0,
        "remaining_time_diarization": 0.0,
    }
    return mock


class TestStreamEndpoint:
    """测试 /ws/transcribe/stream 端点。"""

    @pytest.mark.skip(reason="需要加载真实引擎，跳过单元测试")
    def test_non_wlk_engine_returns_error(self, client):
        """使用非 wlk 引擎时应返回错误。"""
        with client.websocket_connect(
            "/ws/transcribe/stream?api_key=oneasr-key&engine=faster-whisper"
        ) as ws:
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "不支持流式识别" in data["error"]

    @pytest.mark.skip(reason="需要加载真实引擎，跳过单元测试")
    def test_invalid_engine_returns_error(self, client):
        """使用不存在的引擎时应返回错误。"""
        with client.websocket_connect(
            "/ws/transcribe/stream?api_key=oneasr-key&engine=nonexistent"
        ) as ws:
            msg = ws.receive_json()
            # 可能是引擎加载错误或其他错误
            assert msg["type"] == "error"

    @patch("app.engines.wlk_engine.WLKEngine.create_audio_processor")
    def test_wlk_engine_config_message(self, mock_create, client):
        """连接后应收到 config 消息。"""
        mock_processor = MagicMock()
        mock_processor.is_pcm_input = False
        mock_processor.create_tasks = AsyncMock(return_value=self._empty_generator())
        mock_processor.process_audio = AsyncMock()
        mock_processor.cleanup = AsyncMock()
        mock_create.return_value = mock_processor

        # Mock the get_engine to return a mock WLKEngine
        with patch("app.api.stream.get_engine") as mock_get_engine:
            mock_engine = MagicMock(spec=WLKEngine)
            mock_engine.create_audio_processor.return_value = mock_processor
            mock_get_engine.return_value = mock_engine

            with client.websocket_connect(
                "/ws/transcribe/stream?api_key=oneasr-key&engine=wlk"
            ) as ws:
                config_msg = ws.receive_json()
                assert config_msg["type"] == "config"
                assert "useAudioWorklet" in config_msg
                assert config_msg["mode"] == "full"

    @patch("app.engines.wlk_engine.WLKEngine.create_audio_processor")
    def test_wlk_engine_sends_audio(self, mock_create, client):
        """发送音频数据后应收到识别结果。"""
        mock_front_data = _make_mock_front_data()

        async def result_gen():
            yield mock_front_data

        mock_processor = MagicMock()
        mock_processor.is_pcm_input = False
        mock_processor.create_tasks = AsyncMock(return_value=result_gen())
        mock_processor.process_audio = AsyncMock()
        mock_processor.cleanup = AsyncMock()
        mock_create.return_value = mock_processor

        # Mock the get_engine to return a mock WLKEngine
        with patch("app.api.stream.get_engine") as mock_get_engine:
            mock_engine = MagicMock(spec=WLKEngine)
            mock_engine.create_audio_processor.return_value = mock_processor
            mock_get_engine.return_value = mock_engine

            with client.websocket_connect(
                "/ws/transcribe/stream?api_key=oneasr-key&engine=wlk"
            ) as ws:
                # 读取 config 消息
                ws.receive_json()

                # 发送音频数据
                ws.send_bytes(b"\x00\x01" * 100)

                # 读取结果
                result = ws.receive_json()
                assert result["status"] == "active_transcription"
                assert len(result["lines"]) == 1
                assert result["lines"][0]["text"] == "你好世界"
                assert result["lines"][0]["speaker"] == 1
                assert result["buffer_transcription"] == "测试"

    @staticmethod
    async def _empty_generator():
        """空的异步生成器，用于模拟无结果的情况。"""
        if False:
            yield


class TestWLKStreamResponse:
    """测试 WLKStreamResponse 数据模型。"""

    def test_schema_structure(self):
        """验证响应模型的字段。"""
        from app.models.schemas import WLKStreamResponse, StreamLine

        line = StreamLine(speaker=1, text="你好", start="0:00:01.00", end="0:00:02.00")
        resp = WLKStreamResponse(
            status="active_transcription",
            lines=[line],
            buffer_transcription="测试",
        )

        data = resp.model_dump()
        assert data["status"] == "active_transcription"
        assert len(data["lines"]) == 1
        assert data["lines"][0]["text"] == "你好"
        assert data["lines"][0]["speaker"] == 1
        assert data["buffer_transcription"] == "测试"

    def test_schema_defaults(self):
        """验证默认值。"""
        from app.models.schemas import WLKStreamResponse

        resp = WLKStreamResponse()
        assert resp.status == "active_transcription"
        assert resp.lines == []
        assert resp.buffer_transcription == ""
        assert resp.error == ""


class TestWLKEngineConfig:
    """测试 WLKEngine 配置构建。"""

    def test_build_wlk_config_defaults(self):
        """验证默认配置构建。"""
        from app.engines.wlk_engine import WLKEngine
        from app.core.config import EngineConfig

        config = EngineConfig("wlk", {
            "type": "local",
            "model_name": "base",
            "backend": "auto",
            "backend_policy": "simulstreaming",
            "language": "auto",
            "vac": True,
            "diarization": False,
            "pcm_input": False,
        }, model_dir=None)

        engine = WLKEngine(config)
        wlk_config = engine._build_wlk_config()

        assert wlk_config.model_size == "base"
        assert wlk_config.backend == "auto"
        assert wlk_config.backend_policy == "simulstreaming"
        assert wlk_config.lan == "auto"
        assert wlk_config.vac is True
        assert wlk_config.diarization is False
        assert wlk_config.pcm_input is False

    def test_build_wlk_config_with_language_override(self):
        """验证语言覆盖。"""
        from app.engines.wlk_engine import WLKEngine
        from app.core.config import EngineConfig

        config = EngineConfig("wlk", {
            "type": "local",
            "model_name": "base",
            "language": "auto",
        }, model_dir=None)

        engine = WLKEngine(config)
        wlk_config = engine._build_wlk_config(language="zh")

        assert wlk_config.lan == "zh"

    def test_parse_time(self):
        """验证时间解析。"""
        from app.engines.wlk_engine import WLKEngine

        assert WLKEngine._parse_time("0:00:05.30") == 5.30
        assert WLKEngine._parse_time("1:30:00.00") == 5400.0
        assert WLKEngine._parse_time("0:05:10.50") == 310.50


class TestWLKStreamIntegration:
    """集成测试：使用真实音频文件测试 WebSocket 流式识别。"""

    @pytest.mark.integration
    def test_stream_with_real_audio_file(self):
        """使用真实音频文件测试流式识别。"""
        if not TEST_AUDIO_FILE.exists():
            pytest.skip(f"测试文件不存在: {TEST_AUDIO_FILE}")

        results = []
        config_received = False
        ready_to_stop = False

        with TestClient(app) as client:
            with client.websocket_connect(
                "/ws/transcribe/stream?api_key=oneasr-key&engine=wlk&language=auto"
            ) as ws:
                # 接收配置消息
                config_msg = ws.receive_json()
                assert config_msg["type"] == "config"
                config_received = True
                print(f"收到配置: {config_msg}")

                # 读取音频文件
                audio_data = TEST_AUDIO_FILE.read_bytes()
                print(f"音频文件大小: {len(audio_data)} 字节")

                # 分块发送音频数据（每块 32KB）
                chunk_size = 32000
                total_chunks = (len(audio_data) + chunk_size - 1) // chunk_size
                print(f"分 {total_chunks} 块发送")

                for i in range(total_chunks):
                    start = i * chunk_size
                    end = min(start + chunk_size, len(audio_data))
                    chunk = audio_data[start:end]
                    ws.send_bytes(chunk)

                # 发送结束信号
                ws.send_bytes(b"")

                # 接收识别结果
                while True:
                    try:
                        msg = ws.receive_json()
                        if msg.get("type") == "ready_to_stop":
                            ready_to_stop = True
                            print("收到识别完成信号")
                            break
                        elif msg.get("type") == "error":
                            pytest.fail(f"识别错误: {msg.get('error')}")
                        else:
                            results.append(msg)
                            if "lines" in msg and msg["lines"]:
                                print(f"收到结果: {len(msg['lines'])} 行")
                    except Exception as e:
                        print(f"接收消息异常: {e}")
                        break

        assert config_received, "未收到配置消息"
        assert ready_to_stop, "未收到识别完成信号"
        assert len(results) > 0, "未收到识别结果"

        # 验证结果格式
        last_result = results[-1]
        assert "status" in last_result
        assert "lines" in last_result
        print(f"\n识别完成，共收到 {len(results)} 条结果")
        if last_result["lines"]:
            print(f"最后一行文本: {last_result['lines'][-1].get('text', '')[:100]}...")

    @pytest.mark.integration
    def test_stream_with_wav_file(self):
        """使用 WAV 文件测试流式识别。"""
        wav_path = _create_test_wav(duration_sec=2.0)

        try:
            results = []
            config_received = False
            ready_to_stop = False

            with TestClient(app) as client:
                with client.websocket_connect(
                    "/ws/transcribe/stream?api_key=oneasr-key&engine=wlk&language=auto"
                ) as ws:
                    # 接收配置消息
                    config_msg = ws.receive_json()
                    assert config_msg["type"] == "config"
                    config_received = True

                    # 读取 WAV 文件
                    audio_data = wav_path.read_bytes()
                    print(f"WAV 文件大小: {len(audio_data)} 字节")

                    # 分块发送
                    chunk_size = 32000
                    total_chunks = (len(audio_data) + chunk_size - 1) // chunk_size

                    for i in range(total_chunks):
                        start = i * chunk_size
                        end = min(start + chunk_size, len(audio_data))
                        ws.send_bytes(audio_data[start:end])

                    # 发送结束信号
                    ws.send_bytes(b"")

                    # 接收结果
                    while True:
                        try:
                            msg = ws.receive_json()
                            if msg.get("type") == "ready_to_stop":
                                ready_to_stop = True
                                break
                            elif msg.get("type") == "error":
                                print(f"错误: {msg.get('error')}")
                                break
                            else:
                                results.append(msg)
                        except Exception:
                            break

            assert config_received, "未收到配置消息"
            print(f"WAV 测试完成，收到 {len(results)} 条结果")

        finally:
            wav_path.unlink(missing_ok=True)

    @pytest.mark.integration
    def test_stream_api_key_validation(self):
        """测试 API Key 验证。"""
        with TestClient(app) as client:
            # 使用无效的 API Key
            with client.websocket_connect(
                "/ws/transcribe/stream?api_key=invalid-key&engine=wlk"
            ) as ws:
                msg = ws.receive_json()
                assert msg["type"] == "error"
                assert "API Key" in msg["error"]
                print(f"API Key 验证测试通过: {msg['error']}")

    @pytest.mark.integration
    def test_stream_engine_validation(self):
        """测试引擎验证。"""
        import socket
        socket.setdefaulttimeout(5.0)

        try:
            with TestClient(app) as client:
                # 使用不支持的引擎
                with client.websocket_connect(
                    "/ws/transcribe/stream?api_key=oneasr-key&engine=faster-whisper"
                ) as ws:
                    msg = ws.receive_json()
                    assert msg["type"] == "error"
                    assert "不支持流式识别" in msg["error"]
                    print(f"引擎验证测试通过: {msg['error']}")
        finally:
            socket.setdefaulttimeout(None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
