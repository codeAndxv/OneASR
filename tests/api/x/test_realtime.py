"""测试 OneASR 扩展版 /v1/x/realtime WebSocket 端点（支持 sentence 事件与时间戳）。"""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.api


class TestRealtimeExtEndpoint:
    """测试 /v1/x/realtime 扩展端点。"""

    def test_session_update_ext(self, client):
        """发送 session.update 应成功配置扩展会话。"""
        mock_processor = MagicMock()
        mock_processor.is_pcm_input = False
        mock_processor.create_tasks = AsyncMock()
        mock_processor.process_audio = AsyncMock()
        mock_processor.cleanup = AsyncMock()
        mock_processor.is_stopping = True
        mock_task = MagicMock()
        mock_task.done.return_value = True
        mock_processor.transcription_task = mock_task
        mock_processor.total_pcm_samples = 16000
        mock_processor.sample_rate = 16000
        mock_processor.current_silence = 0.0

        mock_alignment = MagicMock()
        mock_alignment.update = MagicMock()
        mock_alignment.get_lines.return_value = ([], [], [])
        mock_processor.tokens_alignment = mock_alignment

        mock_state = MagicMock()
        mock_state.buffer_transcription = None
        mock_processor.get_current_state = AsyncMock(return_value=mock_state)

        with patch("server.api.x.realtime.get_engine") as mock_get_engine:
            mock_engine = MagicMock()
            mock_engine.create_audio_processor.return_value = mock_processor
            mock_get_engine.return_value = mock_engine

            with client.websocket_connect("/v1/x/realtime?api_key=oneasr-key") as ws:
                created_msg = ws.receive_json()
                assert created_msg["type"] == "session.created"

                ws.send_json({
                    "type": "session.update",
                    "session": {
                        "type": "transcription",
                        "audio": {
                            "input": {
                                "format": {"type": "audio/pcm", "rate": 16000},
                                "transcription": {
                                    "model": "faster-whisper",
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

                ws.send_json({
                    "type": "input_audio_buffer.append",
                    "audio": base64.b64encode(b"\x00\x00" * 800).decode(),
                })

                ws.send_json({"type": "input_audio_buffer.commit"})
                done_msg = ws.receive_json()
                assert done_msg["type"] == "done"

    def test_inband_auth_pure_url_success(self, client):
        """测试纯净 URL (零参数零Header)，通过首帧 session.update 传递 api_key 鉴权成功。"""
        mock_processor = MagicMock()
        mock_processor.is_pcm_input = False
        mock_processor.create_tasks = AsyncMock()
        mock_processor.process_audio = AsyncMock()
        mock_processor.cleanup = AsyncMock()
        mock_processor.is_stopping = True
        mock_task = MagicMock()
        mock_task.done.return_value = True
        mock_processor.transcription_task = mock_task
        mock_processor.total_pcm_samples = 16000
        mock_processor.sample_rate = 16000
        mock_processor.current_silence = 0.0

        mock_alignment = MagicMock()
        mock_alignment.update = MagicMock()
        mock_alignment.get_lines.return_value = ([], [], [])
        mock_processor.tokens_alignment = mock_alignment

        mock_state = MagicMock()
        mock_state.buffer_transcription = None
        mock_processor.get_current_state = AsyncMock(return_value=mock_state)

        with patch("server.api.x.realtime.get_engine") as mock_get_engine:
            mock_engine = MagicMock()
            mock_engine.create_audio_processor.return_value = mock_processor
            mock_get_engine.return_value = mock_engine

            # 纯净 URL，无 query_params，无 headers
            with client.websocket_connect("/v1/x/realtime") as ws:
                created_msg = ws.receive_json()
                assert created_msg["type"] == "session.created"

                ws.send_json({
                    "type": "session.update",
                    "session": {
                        "api_key": "oneasr-key",
                        "type": "transcription",
                        "audio": {
                            "input": {
                                "format": {"type": "audio/pcm", "rate": 16000},
                                "transcription": {
                                    "model": "faster-whisper",
                                    "language": "zh",
                                },
                            },
                        },
                    },
                })

                msg = ws.receive_json()
                assert msg["type"] == "session.updated"
                assert msg["session"]["id"] is not None

    def test_inband_auth_pure_url_invalid_key(self, client):
        """测试纯净 URL 下首帧 api_key 错误被拒绝。"""
        with client.websocket_connect("/v1/x/realtime") as ws:
            created_msg = ws.receive_json()
            assert created_msg["type"] == "session.created"

            ws.send_json({
                "type": "session.update",
                "session": {
                    "api_key": "wrong-key",
                    "type": "transcription",
                },
            })
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["error"]["code"] == "invalid_api_key"

    def test_parse_time_to_seconds(self):
        """测试时间格式解析工具。"""
        from server.api.x.realtime import _parse_time_to_seconds
        assert _parse_time_to_seconds(1.23) == 1.23
        assert _parse_time_to_seconds("0:00:01.50") == 1.50
        assert _parse_time_to_seconds("0:01:30.00") == 90.00
        assert _parse_time_to_seconds("1:00:00.00") == 3600.00
        assert _parse_time_to_seconds(None) == 0.0
        assert _parse_time_to_seconds("invalid") == 0.0
