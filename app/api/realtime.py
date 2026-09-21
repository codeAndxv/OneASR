"""OpenAI Realtime Transcription 风格的 WebSocket 流式语音识别接口。

支持两种引擎模式：
1. 本地处理器模式（WhisperLiveKit 等，通过 create_audio_processor）
2. X-ASR 原生流式模式（通过 create_stream_session，基于 sherpa-onnx）
"""

import asyncio
import base64
import json
import logging
import time
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.auth import verify_ws_api_key
from app.engines.registry import get_engine
from app.services.record_service import save_streaming_record

logger = logging.getLogger(__name__)

router = APIRouter(tags=["realtime"])


class SessionState:
    IDLE = "idle"
    CONFIGURED = "configured"
    LISTENING = "listening"
    FINALIZING = "finalizing"

    def __init__(self):
        self.state = self.IDLE
        self.session_id = str(uuid.uuid4())
        self.language: str | None = None
        self.model: str | None = None
        self.delay: str | None = None
        self.item_counter = 0
        self.transcript_parts: list[str] = []

    def next_item_id(self) -> str:
        self.item_counter += 1
        return f"item_{self.session_id[:8]}_{self.item_counter}"


# ═══════════════════════════════════════════════════════════════════
#  X-ASR 原生流式模式（sherpa-onnx）
# ═══════════════════════════════════════════════════════════════════

async def _xasr_session(
    ws: WebSocket,
    eng,
    session: SessionState,
    send_event,
    send_error,
):
    """X-ASR 原生流式识别会话。

    使用 eng.create_stream_session() 创建 sherpa-onnx 会话，
    在主循环中处理音频和获取结果。
    """
    stream_session = eng.create_stream_session()

    session.state = SessionState.CONFIGURED

    # 发送 session.updated 确认
    await send_event({
        "type": "session.updated",
        "session": {
            "id": session.session_id,
            "type": "transcription",
            "audio": {
                "input": {
                    "format": {"type": "audio/pcm", "rate": eng.sample_rate},
                    "transcription": {
                        "model": session.model or "xasr",
                        "language": session.language,
                    },
                },
            },
        },
    })

    try:
        while True:
            raw = await ws.receive_text()
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                await send_error("invalid_message", "Failed to parse JSON message")
                continue

            event_type = event.get("type")

            if event_type == "input_audio_buffer.append":
                audio_b64 = event.get("audio", "")
                if not audio_b64:
                    continue

                try:
                    audio_bytes = base64.b64decode(audio_b64)
                except Exception:
                    await send_error("invalid_audio", "Failed to decode base64 audio data")
                    continue

                if session.state == SessionState.CONFIGURED:
                    session.state = SessionState.LISTENING

                # 送入 sherpa-onnx 识别
                stream_session.accept_audio(audio_bytes)
                stream_session.decode()

                # 发送 partial 结果
                partial = stream_session.get_partial_result()
                if partial:
                    item_id = session.next_item_id()
                    await send_event({
                        "type": "conversation.item.input_audio_transcription.delta",
                        "item_id": item_id,
                        "content_index": 0,
                        "delta": partial,
                    })

                # 检测端点（如果启用了 endpoint detection）
                if stream_session.is_endpoint():
                    session.transcript_parts.append(stream_session.get_full_text())

            elif event_type == "input_audio_buffer.commit":
                if session.state != SessionState.LISTENING:
                    await send_error("invalid_state", "No active transcription session")
                    continue

                session.state = SessionState.FINALIZING

                # 获取最终结果
                final_text = stream_session.finalize()
                if final_text:
                    session.transcript_parts.append(final_text)
                    item_id = session.next_item_id()
                    await send_event({
                        "type": "conversation.item.input_audio_transcription.delta",
                        "item_id": item_id,
                        "content_index": 0,
                        "delta": final_text,
                    })
                    await send_event({
                        "type": "conversation.item.input_audio_transcription.completed",
                        "item_id": item_id,
                        "content_index": 0,
                        "transcript": final_text,
                    })

                await send_event({"type": "done"})
                await ws.close()
                return

            elif event_type == "session.update":
                pass  # 已配置，忽略重复更新

            else:
                logger.debug("[xasr] 未知事件类型: %s", event_type)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("[xasr] 会话异常: %s", e, exc_info=True)
        await send_error("session_error", str(e))


# ═══════════════════════════════════════════════════════════════════
#  主端点
# ═══════════════════════════════════════════════════════════════════

@router.websocket("/v1/realtime")
async def realtime_transcription(ws: WebSocket):
    """OpenAI Realtime Transcription 风格的 WebSocket 接口。"""
    try:
        await ws.accept()
    except Exception as e:
        logger.warning("接受 WebSocket 连接失败: %s", e)
        return

    if not verify_ws_api_key(ws):
        try:
            await ws.send_json({"type": "error", "error": {"code": "invalid_api_key", "message": "Invalid API key"}})
            await ws.close()
        except Exception:
            pass
        return

    session = SessionState()
    processor = None
    eng = None
    results_task = None
    heartbeat_task = None
    t_start = time.time()
    record_id = str(uuid.uuid4())

    async def _send_event(event: dict):
        try:
            await ws.send_json(event)
        except Exception:
            pass

    async def _send_error(code: str, message: str):
        await _send_event({"type": "error", "error": {"code": code, "message": message}})

    async def _handle_session_update(data: dict):
        nonlocal processor, eng, results_task, heartbeat_task
        sess_cfg = data.get("session", {})

        audio_input = sess_cfg.get("audio", {}).get("input", {})
        format_cfg = audio_input.get("format", {})
        transcription_cfg = audio_input.get("transcription", {})

        session.language = transcription_cfg.get("language")
        session.model = transcription_cfg.get("model")
        session.delay = transcription_cfg.get("delay")

        engine_name = session.model
        try:
            eng = get_engine(engine_name)
        except Exception as e:
            await _send_error("engine_error", f"Failed to load engine: {e}")
            return

        # ── X-ASR 原生流式模式 ──
        if hasattr(eng, "create_stream_session"):
            await _xasr_session(ws, eng, session, _send_event, _send_error)
            return

        # ── 本地处理器模式 ──
        try:
            processor = await asyncio.to_thread(eng.create_audio_processor, language=session.language, pcm_input=True)
        except Exception as e:
            await _send_error("processor_error", f"Failed to create AudioProcessor: {e}")
            return

        session.state = SessionState.CONFIGURED
        await processor.create_tasks()
        results_task = asyncio.create_task(_forward_results(None))
        heartbeat_task = asyncio.create_task(_heartbeat())

        await _send_event({
            "type": "session.updated",
            "session": {
                "id": session.session_id,
                "type": "transcription",
                "audio": {
                    "input": {
                        "format": format_cfg or {"type": "audio/pcm", "rate": 16000},
                        "transcription": {
                            "model": session.model or "whisper1",
                            "language": session.language,
                            "delay": session.delay,
                        },
                    },
                },
            },
        })

    async def _forward_results(_ignored_gen):
        """直接从 AudioProcessor 读取状态。"""
        sent_texts: set[str] = set()
        last_buffer = ""
        try:
            while True:
                if processor.is_stopping:
                    if processor.transcription_task and processor.transcription_task.done():
                        break

                processor.tokens_alignment.update()
                lines, _, _ = processor.tokens_alignment.get_lines(
                    diarization=False,
                    current_silence=processor.current_silence,
                    audio_time=processor.total_pcm_samples / processor.sample_rate if processor.sample_rate else None,
                )
                state = await processor.get_current_state()
                buffer_text = (state.buffer_transcription.text if state.buffer_transcription else "").strip()

                for line in lines:
                    text = (line.text or "").strip()
                    if not text or getattr(line, "speaker", None) == -2:
                        continue
                    if text in sent_texts:
                        continue
                    sent_texts.add(text)
                    item_id = session.next_item_id()
                    await _send_event({"type": "conversation.item.input_audio_transcription.delta", "item_id": item_id, "content_index": 0, "delta": text})
                    session.transcript_parts.append(text)
                    await _send_event({"type": "conversation.item.input_audio_transcription.completed", "item_id": item_id, "content_index": 0, "transcript": text})

                if buffer_text != last_buffer:
                    if buffer_text:
                        item_id = session.next_item_id()
                        await _send_event({"type": "conversation.item.input_audio_transcription.delta", "item_id": item_id, "content_index": 0, "delta": buffer_text})
                    last_buffer = buffer_text

                await asyncio.sleep(0.1)

        except WebSocketDisconnect:
            pass
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception("Realtime 结果处理异常: %s", e)

    async def _heartbeat():
        while True:
            await asyncio.sleep(5.0)
            await _send_event({"type": "heartbeat"})

    try:
        while True:
            raw = await ws.receive_text()
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                await _send_error("invalid_message", "Failed to parse JSON message")
                continue

            event_type = event.get("type")

            if event_type == "session.update":
                await _handle_session_update(event)
                # X-ASR 模式下 _handle_session_update 不会返回
                # 因为它进入了 _xasr_session 的主循环

            elif event_type == "input_audio_buffer.append":
                if processor is None:
                    await _send_error("invalid_state", "Please send session.update to configure session first")
                    continue

                audio_b64 = event.get("audio", "")
                if not audio_b64:
                    continue

                try:
                    audio_bytes = base64.b64decode(audio_b64)
                except Exception:
                    await _send_error("invalid_audio", "Failed to decode base64 audio data")
                    continue

                if session.state == SessionState.CONFIGURED:
                    session.state = SessionState.LISTENING

                await processor.process_audio(audio_bytes)

            elif event_type == "input_audio_buffer.commit":
                if processor is None or session.state != SessionState.LISTENING:
                    await _send_error("invalid_state", "No active transcription session")
                    continue

                session.state = SessionState.FINALIZING
                await processor.process_audio(b"")

                if results_task and not results_task.done():
                    try:
                        await asyncio.wait_for(results_task, timeout=30.0)
                    except asyncio.TimeoutError:
                        results_task.cancel()

                await _send_event({"type": "done"})
                await ws.close()
                return

            else:
                logger.debug("未知事件类型: %s", event_type)

    except WebSocketDisconnect:
        logger.info("Realtime 客户端断开连接: session_id=%s", session.session_id)
    except Exception as e:
        logger.error("Realtime WebSocket 异常: %s", e, exc_info=True)
    finally:
        if heartbeat_task and not heartbeat_task.done():
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

        if results_task and not results_task.done():
            results_task.cancel()
            try:
                await results_task
            except (asyncio.CancelledError, Exception):
                pass

        if processor:
            try:
                await processor.cleanup()
            except Exception:
                pass

        eng_model = eng.model_name if hasattr(eng, "model_name") else None
        await save_streaming_record(
            record_id=record_id,
            engine_name=session.model or "whisper1",
            model_name=eng_model,
            language=session.language,
            line_count=len(session.transcript_parts),
            total_time=time.time() - t_start,
            is_completed=session.state == SessionState.FINALIZING,
        )
