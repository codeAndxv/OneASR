"""测试 OpenAI Realtime Transcription 风格的 /v1/realtime WebSocket 端点。"""

import base64
from unittest.mock import MagicMock, patch

import pytest

from tests.helpers.mock_engines import MockStreamSession

pytestmark = pytest.mark.api


class TestRealtimeEndpoint:
    """测试 /v1/realtime 端点。"""

    def test_session_update_configures_session(self, client):
        """发送 session.update 应收到 session.updated 响应。"""
        mock_stream = MockStreamSession()
        mock_engine = MagicMock()
        mock_engine.create_stream_session.return_value = mock_stream

        with patch("server.api.standard.realtime.get_engine", return_value=mock_engine):
            with client.websocket_connect("/v1/realtime?api_key=oneasr-key") as ws:
                created_msg = ws.receive_json()
                assert created_msg["type"] == "session.created"
                assert created_msg["session"]["id"] is not None

                ws.send_json({
                    "type": "session.update",
                    "session": {
                        "type": "transcription",
                        "audio": {
                            "input": {
                                "format": {"type": "audio/pcm", "rate": 16000},
                                "transcription": {
                                    "model": "xasr",
                                    "language": "zh",
                                },
                            },
                        },
                    },
                })

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
        mock_stream = MockStreamSession()
        mock_engine = MagicMock()
        mock_engine.create_stream_session.return_value = mock_stream

        with patch("server.api.standard.realtime.get_engine", return_value=mock_engine):
            with client.websocket_connect("/v1/realtime?api_key=oneasr-key") as ws:
                ws.receive_json()

                ws.send_json({
                    "type": "input_audio_buffer.append",
                    "audio": "AAAA",
                })

                msg = ws.receive_json()
                assert msg["type"] == "error"
                assert msg["error"]["code"] == "invalid_state"

    def test_transcription_results_format(self, client):
        """验证转录结果的 OpenAI 事件格式。"""
        mock_stream = MockStreamSession("你好世界。")
        mock_engine = MagicMock()
        mock_engine.create_stream_session.return_value = mock_stream

        with patch("server.api.standard.realtime.get_engine", return_value=mock_engine):
            with client.websocket_connect("/v1/realtime?api_key=oneasr-key") as ws:
                ws.receive_json()

                ws.send_json({
                    "type": "session.update",
                    "session": {
                        "type": "transcription",
                        "audio": {
                            "input": {
                                "transcription": {"model": "xasr"},
                            },
                        },
                    },
                })
                ws.receive_json()  # session.updated

                ws.send_json({
                    "type": "input_audio_buffer.append",
                    "audio": base64.b64encode(b"\x00\x01" * 1600).decode(),
                })

                delta_msg = ws.receive_json()
                assert delta_msg["type"] == "conversation.item.input_audio_transcription.delta"
                assert "你好世界" in delta_msg["delta"]
                assert delta_msg["item_id"] is not None
                assert delta_msg["content_index"] == 0

                completed_msg = ws.receive_json()
                assert completed_msg["type"] == "conversation.item.input_audio_transcription.completed"
                assert "你好世界" in completed_msg["transcript"]
                assert completed_msg["item_id"] is not None

    def test_commit_triggers_finalization(self, client):
        """发送 commit 应触发流结束。"""
        mock_stream = MockStreamSession("你好世界。")
        mock_engine = MagicMock()
        mock_engine.create_stream_session.return_value = mock_stream

        with patch("server.api.standard.realtime.get_engine", return_value=mock_engine):
            with client.websocket_connect("/v1/realtime?api_key=oneasr-key") as ws:
                ws.receive_json()

                ws.send_json({
                    "type": "session.update",
                    "session": {
                        "type": "transcription",
                        "audio": {
                            "input": {
                                "transcription": {"model": "xasr"},
                            },
                        },
                    },
                })
                ws.receive_json()

                ws.send_json({
                    "type": "input_audio_buffer.append",
                    "audio": base64.b64encode(b"\x00\x00" * 1600).decode(),
                })

                ws.receive_json()  # delta
                ws.receive_json()  # completed

                ws.send_json({"type": "input_audio_buffer.commit"})

    def test_commit_without_listening_returns_error(self, client):
        """在非 LISTENING 状态下 commit 应返回错误。"""
        mock_stream = MockStreamSession()
        mock_engine = MagicMock()
        mock_engine.create_stream_session.return_value = mock_stream

        with patch("server.api.standard.realtime.get_engine", return_value=mock_engine):
            with client.websocket_connect("/v1/realtime?api_key=oneasr-key") as ws:
                ws.receive_json()

                ws.send_json({
                    "type": "session.update",
                    "session": {
                        "type": "transcription",
                        "audio": {
                            "input": {
                                "transcription": {"model": "xasr"},
                            },
                        },
                    },
                })
                ws.receive_json()

                ws.send_json({"type": "input_audio_buffer.commit"})

                msg = ws.receive_json()
                assert msg["type"] == "error"
                assert msg["error"]["code"] == "invalid_state"


class TestRealtimeProtocol:
    """测试 Realtime 协议的消息格式。"""

    def test_session_update_requires_session_field(self, client):
        """session.update 缺省 session 时使用默认配置。"""
        mock_stream = MockStreamSession()
        mock_engine = MagicMock()
        mock_engine.create_stream_session.return_value = mock_stream

        with patch("server.api.standard.realtime.get_engine", return_value=mock_engine):
            with client.websocket_connect("/v1/realtime?api_key=oneasr-key") as ws:
                created = ws.receive_json()
                assert created["type"] == "session.created"

                ws.send_json({"type": "session.update"})
                updated = ws.receive_json()
                assert updated["type"] == "session.updated"
