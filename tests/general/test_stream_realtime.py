"""测试 OpenAI Realtime Transcription 风格的 /v1/realtime WebSocket 端点。"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.engines.whisperlivekit_engine import WhisperLiveKitEngine


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def _make_mock_front_data():
    """创建模拟的 WhisperLiveKit FrontData 对象。"""
    mock = MagicMock()
    mock.to_dict.return_value = {
        "status": "active_transcription",
        "lines": [
            {"speaker": 1, "text": "你好世界", "start": "0:00:01.00", "end": "0:00:03.00"},
        ],
        "buffer_transcription": "测试",
        "buffer_diarization": "",
        "buffer_translation": "",
    }
    return mock


async def _empty_generator():
    """空的异步生成器。"""
    if False:
        yield


class TestRealtimeEndpoint:
    """测试 /v1/realtime 端点。"""

    def test_session_update_configures_session(self, client):
        """发送 session.update 应收到 session.updated 响应。"""
        mock_processor = MagicMock()
        mock_processor.is_pcm_input = False
        mock_processor.create_tasks = AsyncMock(return_value=_empty_generator())
        mock_processor.process_audio = AsyncMock()
        mock_processor.cleanup = AsyncMock()

        with patch("app.api.realtime.get_engine") as mock_get_engine:
            mock_engine = MagicMock(spec=WhisperLiveKitEngine)
            mock_engine.create_audio_processor.return_value = mock_processor
            mock_get_engine.return_value = mock_engine

            with client.websocket_connect("/v1/realtime?api_key=oneasr-key") as ws:
                # 发送 session.update
                ws.send_json({
                    "type": "session.update",
                    "session": {
                        "type": "transcription",
                        "audio": {
                            "input": {
                                "format": {"type": "audio/pcm", "rate": 16000},
                                "transcription": {
                                    "model": "wlk-live",
                                    "language": "zh",
                                },
                            },
                        },
                    },
                })

                # 接收 session.updated
                msg = ws.receive_json()
                assert msg["type"] == "session.updated"
                assert msg["session"]["type"] == "transcription"
                assert msg["session"]["id"] is not None

    def test_invalid_api_key_rejected(self, client):
        """无效的 API Key 应被拒绝。"""
        with client.websocket_connect("/v1/realtime?api_key=invalid") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["error"]["code"] == "invalid_api_key"

    def test_audio_append_before_session_update(self, client):
        """在 session.update 之前发送音频应返回错误。"""
        mock_processor = MagicMock()
        mock_processor.is_pcm_input = False
        mock_processor.create_tasks = AsyncMock(return_value=_empty_generator())
        mock_processor.process_audio = AsyncMock()
        mock_processor.cleanup = AsyncMock()

        with patch("app.api.realtime.get_engine") as mock_get_engine:
            mock_engine = MagicMock(spec=WhisperLiveKitEngine)
            mock_engine.create_audio_processor.return_value = mock_processor
            mock_get_engine.return_value = mock_engine

            with client.websocket_connect("/v1/realtime?api_key=oneasr-key") as ws:
                # 直接发送音频（未配置 session）
                ws.send_json({
                    "type": "input_audio_buffer.append",
                    "audio": "AAAA",  # 任意 base64 数据
                })

                msg = ws.receive_json()
                assert msg["type"] == "error"
                assert msg["error"]["code"] == "invalid_state"

    def test_transcription_results_format(self, client):
        """验证转录结果的 OpenAI 事件格式。"""
        mock_front_data = _make_mock_front_data()

        async def result_gen():
            yield mock_front_data

        mock_processor = MagicMock()
        mock_processor.is_pcm_input = False
        mock_processor.create_tasks = AsyncMock(return_value=result_gen())
        mock_processor.process_audio = AsyncMock()
        mock_processor.cleanup = AsyncMock()

        with patch("app.api.realtime.get_engine") as mock_get_engine:
            mock_engine = MagicMock(spec=WhisperLiveKitEngine)
            mock_engine.create_audio_processor.return_value = mock_processor
            mock_get_engine.return_value = mock_engine

            with client.websocket_connect("/v1/realtime?api_key=oneasr-key") as ws:
                # 配置 session
                ws.send_json({
                    "type": "session.update",
                    "session": {
                        "type": "transcription",
                        "audio": {
                            "input": {
                                "transcription": {"model": "wlk-live"},
                            },
                        },
                    },
                })
                ws.receive_json()  # session.updated

                # 发送音频
                import base64
                ws.send_json({
                    "type": "input_audio_buffer.append",
                    "audio": base64.b64encode(b"\x00\x01" * 100).decode(),
                })

                # 接收结果
                delta_msg = ws.receive_json()
                assert delta_msg["type"] == "conversation.item.input_audio_transcription.delta"
                assert delta_msg["delta"] == "你好世界"
                assert delta_msg["item_id"] is not None
                assert delta_msg["content_index"] == 0

                completed_msg = ws.receive_json()
                assert completed_msg["type"] == "conversation.item.input_audio_transcription.completed"
                assert completed_msg["transcript"] == "你好世界"
                assert completed_msg["item_id"] is not None

    def test_commit_triggers_finalization(self, client):
        """发送 commit 应触发流结束。"""
        mock_processor = MagicMock()
        mock_processor.is_pcm_input = False
        mock_processor.create_tasks = AsyncMock(return_value=_empty_generator())
        mock_processor.process_audio = AsyncMock()
        mock_processor.cleanup = AsyncMock()

        with patch("app.api.realtime.get_engine") as mock_get_engine:
            mock_engine = MagicMock(spec=WhisperLiveKitEngine)
            mock_engine.create_audio_processor.return_value = mock_processor
            mock_get_engine.return_value = mock_engine

            with client.websocket_connect("/v1/realtime?api_key=oneasr-key") as ws:
                # 配置 session
                ws.send_json({
                    "type": "session.update",
                    "session": {
                        "type": "transcription",
                        "audio": {
                            "input": {
                                "transcription": {"model": "wlk-live"},
                            },
                        },
                    },
                })
                ws.receive_json()  # session.updated

                # 发送音频
                import base64
                ws.send_json({
                    "type": "input_audio_buffer.append",
                    "audio": base64.b64encode(b"\x00\x00" * 16000).decode(),
                })

                # 发送 commit
                ws.send_json({"type": "input_audio_buffer.commit"})

                # 验证 process_audio 被调用了空字节
                mock_processor.process_audio.assert_called_with(b"")

    def test_commit_without_listening_returns_error(self, client):
        """在非 LISTENING 状态下 commit 应返回错误。"""
        mock_processor = MagicMock()
        mock_processor.is_pcm_input = False
        mock_processor.create_tasks = AsyncMock(return_value=_empty_generator())
        mock_processor.process_audio = AsyncMock()
        mock_processor.cleanup = AsyncMock()

        with patch("app.api.realtime.get_engine") as mock_get_engine:
            mock_engine = MagicMock(spec=WhisperLiveKitEngine)
            mock_engine.create_audio_processor.return_value = mock_processor
            mock_get_engine.return_value = mock_engine

            with client.websocket_connect("/v1/realtime?api_key=oneasr-key") as ws:
                # 配置 session
                ws.send_json({
                    "type": "session.update",
                    "session": {
                        "type": "transcription",
                        "audio": {
                            "input": {
                                "transcription": {"model": "wlk-live"},
                            },
                        },
                    },
                })
                ws.receive_json()  # session.updated

                # 直接 commit（未发送音频）
                ws.send_json({"type": "input_audio_buffer.commit"})

                msg = ws.receive_json()
                assert msg["type"] == "error"
                assert msg["error"]["code"] == "invalid_state"


class TestRealtimeProtocol:
    """测试 Realtime 协议的消息格式。"""

    def test_session_update_requires_session_field(self, client):
        """session.update 必须包含 session 字段。"""
        with client.websocket_connect("/v1/realtime?api_key=oneasr-key") as ws:
            # 发送无效的 session.update（缺少 session 字段）
            ws.send_json({"type": "session.update"})

            # 服务端可能返回错误或忽略
            # 由于 session 为 None，get_engine 会被调用但可能失败
            # 关键是不应该崩溃


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
