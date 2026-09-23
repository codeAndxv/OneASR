"""扩展版 Realtime Transcription — 兼容 OpenAI 协议 + OneASR 扩展字段。

路由: WS /v1/realtimeext

扩展特性:
- 新增 sentence 事件: conversation.item.input_audio_transcription.sentence（携带完整文本、start、end 时间戳及 is_endpoint: true）
- delta 事件增加 start、end 时间戳及 is_endpoint 标记
- 支持 language（单语言字符串）与 languages（数组）
- heartbeat 心跳事件（每 5 秒）
- done 事件（commit 完成后通知客户端可关闭）
"""

import asyncio
import base64
import json
import logging
import time
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.auth import verify_ws_api_key
from app.api.realtime import SessionState
from app.engines.registry import get_engine
from app.services.record_service import save_streaming_record
from app.utils.audio_converter import AudioConverter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["realtimeext"])


def _parse_time_to_seconds(val) -> float:
    """将时间字符串（如 '0:00:01.20'）或数字解析为浮点秒数。"""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            parts = val.split(":")
            if len(parts) == 3:
                h, m, s = parts
                return float(h) * 3600 + float(m) * 60 + float(s)
            elif len(parts) == 2:
                m, s = parts
                return float(m) * 60 + float(s)
            return float(val)
        except Exception:
            return 0.0
    return 0.0


# ═══════════════════════════════════════════════════════════════════
#  X-ASR 原生流式扩展模式（sherpa-onnx）
# ═══════════════════════════════════════════════════════════════════

async def _xasr_session_ext(
    ws: WebSocket,
    eng,
    session: SessionState,
    send_event,
    send_error,
):
    """X-ASR 原生流式扩展识别会话。"""
    stream_session = eng.create_stream_session()
    session.state = SessionState.CONFIGURED

    sample_rate = getattr(eng, "sample_rate", 16000) or 16000
    total_samples = 0
    last_sentence_end_time = 0.0

    await send_event({
        "type": "session.updated",
        "session": {
            "id": session.session_id,
            "type": "transcription",
            "audio": {
                "input": {
                    "format": {"type": "audio/pcm", "rate": sample_rate},
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

                audio_bytes = AudioConverter.base64_to_pcm16(audio_b64)
                if not audio_bytes:
                    continue

                total_samples += len(audio_bytes) // 2
                current_time = total_samples / sample_rate

                if session.state == SessionState.CONFIGURED:
                    session.state = SessionState.LISTENING

                stream_session.accept_audio(audio_bytes)
                stream_session.decode()

                # 发送 partial 增量结果
                partial = stream_session.get_partial_result()
                if partial:
                    item_id = session.next_item_id()
                    await send_event({
                        "type": "conversation.item.input_audio_transcription.delta",
                        "item_id": item_id,
                        "content_index": 0,
                        "delta": partial,
                        "start": round(last_sentence_end_time, 2),
                        "end": round(current_time, 2),
                        "is_endpoint": False,
                    })

                # 检测端点
                if stream_session.is_endpoint():
                    text = stream_session.get_full_text()
                    if text:
                        session.transcript_parts.append(text)
                        item_id = session.next_item_id()
                        # 扩展事件：sentence（携带整句完整文本与精准时间戳）
                        await send_event({
                            "type": "conversation.item.input_audio_transcription.sentence",
                            "item_id": item_id,
                            "content_index": 0,
                            "text": text,
                            "transcript": text,
                            "start": round(last_sentence_end_time, 2),
                            "end": round(current_time, 2),
                            "is_endpoint": True,
                        })
                        # 兼容事件：completed
                        await send_event({
                            "type": "conversation.item.input_audio_transcription.completed",
                            "item_id": item_id,
                            "content_index": 0,
                            "transcript": text,
                            "start": round(last_sentence_end_time, 2),
                            "end": round(current_time, 2),
                            "is_endpoint": True,
                        })
                        last_sentence_end_time = current_time
                    stream_session.reset_endpoint()

            elif event_type == "input_audio_buffer.commit":
                if session.state != SessionState.LISTENING:
                    await send_error("invalid_state", "No active transcription session")
                    continue

                session.state = SessionState.FINALIZING
                final_text = stream_session.finalize()
                current_time = total_samples / sample_rate
                if final_text:
                    session.transcript_parts.append(final_text)
                    item_id = session.next_item_id()
                    await send_event({
                        "type": "conversation.item.input_audio_transcription.sentence",
                        "item_id": item_id,
                        "content_index": 0,
                        "text": final_text,
                        "transcript": final_text,
                        "start": round(last_sentence_end_time, 2),
                        "end": round(current_time, 2),
                        "is_endpoint": True,
                    })
                    await send_event({
                        "type": "conversation.item.input_audio_transcription.completed",
                        "item_id": item_id,
                        "content_index": 0,
                        "transcript": final_text,
                        "start": round(last_sentence_end_time, 2),
                        "end": round(current_time, 2),
                        "is_endpoint": True,
                    })

                await send_event({"type": "done"})
                await ws.close()
                return

            elif event_type == "session.update":
                pass

            else:
                logger.debug("[realtimeext-xasr] 未知事件类型: %s", event_type)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("[realtimeext-xasr] 会话异常: %s", e, exc_info=True)
        await send_error("session_error", str(e))


# ═══════════════════════════════════════════════════════════════════
#  主扩展端点 (/v1/realtimeext)
# ═══════════════════════════════════════════════════════════════════

@router.websocket("/v1/realtimeext")
async def realtime_transcription_ext(ws: WebSocket):
    """扩展版 WebSocket 实时转录接口，支持 sentence 事件、时间戳及心跳。"""
    try:
        await ws.accept()
    except Exception as e:
        logger.warning("[realtimeext] 接受 WebSocket 连接失败: %s", e)
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

        # 扩展：支持 language（单字符串）和 languages（数组）
        session.language = transcription_cfg.get("language")
        if not session.language and transcription_cfg.get("languages"):
            langs = transcription_cfg["languages"]
            session.language = langs[0] if isinstance(langs, list) else langs
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
            await _xasr_session_ext(ws, eng, session, _send_event, _send_error)
            return

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
        """从 AudioProcessor 读取转录结果，发送带有精准时间戳的 delta/sentence/completed 事件。"""
        sent_texts: set[str] = set()
        last_buffer = ""
        last_completed_end_time = 0.0

        try:
            while True:
                if processor.is_stopping:
                    if processor.transcription_task and processor.transcription_task.done():
                        break

                processor.tokens_alignment.update()
                audio_time = processor.total_pcm_samples / processor.sample_rate if processor.sample_rate else 0.0
                lines, _, _ = processor.tokens_alignment.get_lines(
                    diarization=False,
                    current_silence=processor.current_silence,
                    audio_time=audio_time,
                )
                state = await processor.get_current_state()
                buffer_text = (state.buffer_transcription.text if state.buffer_transcription else "").strip()

                # 已确认定稿的整句：发送 sentence 与 completed
                for line in lines:
                    text = (line.text or "").strip()
                    if not text or getattr(line, "speaker", None) == -2:
                        continue
                    if text in sent_texts:
                        continue
                    sent_texts.add(text)

                    line_start = _parse_time_to_seconds(getattr(line, "start", None)) or last_completed_end_time
                    line_end = _parse_time_to_seconds(getattr(line, "end", None)) or audio_time
                    last_completed_end_time = line_end

                    item_id = session.next_item_id()

                    # 1. 扩展事件：sentence 整句定稿事件（包含完整文本、真实起止时间戳、is_endpoint: true）
                    await _send_event({
                        "type": "conversation.item.input_audio_transcription.sentence",
                        "item_id": item_id,
                        "content_index": 0,
                        "text": text,
                        "transcript": text,
                        "start": round(line_start, 2),
                        "end": round(line_end, 2),
                        "is_endpoint": True,
                    })

                    session.transcript_parts.append(text)

                    # 2. 兼容事件：completed
                    await _send_event({
                        "type": "conversation.item.input_audio_transcription.completed",
                        "item_id": item_id,
                        "content_index": 0,
                        "transcript": text,
                        "start": round(line_start, 2),
                        "end": round(line_end, 2),
                        "is_endpoint": True,
                    })

                # 实时缓冲文本变化（发送 delta 增量/临时草稿）
                if buffer_text != last_buffer:
                    if buffer_text:
                        item_id = session.next_item_id()
                        await _send_event({
                            "type": "conversation.item.input_audio_transcription.delta",
                            "item_id": item_id,
                            "content_index": 0,
                            "delta": buffer_text,
                            "start": round(last_completed_end_time, 2),
                            "end": round(audio_time, 2),
                            "is_endpoint": False,
                        })
                    last_buffer = buffer_text

                await asyncio.sleep(0.1)

        except WebSocketDisconnect:
            pass
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception("[realtimeext] 结果处理异常: %s", e)

    async def _heartbeat():
        """扩展：每 5 秒发送心跳事件。"""
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
                # X-ASR 模式下会话已由 _xasr_session_ext 处理完毕
                if eng is not None and hasattr(eng, "create_stream_session"):
                    return

            elif event_type == "input_audio_buffer.append":
                if processor is None:
                    await _send_error("invalid_state", "Please send session.update to configure session first")
                    continue

                audio_b64 = event.get("audio", "")
                if not audio_b64:
                    continue

                audio_bytes = AudioConverter.base64_to_pcm16(audio_b64)
                if not audio_bytes:
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

                # 扩展：发送 done 事件通知客户端可关闭
                await _send_event({"type": "done"})
                await ws.close()
                return

            else:
                logger.debug("[realtimeext] 未知事件类型: %s", event_type)

    except WebSocketDisconnect:
        logger.info("[realtimeext] 客户端断开连接: session_id=%s", session.session_id)
    except Exception as e:
        logger.error("[realtimeext] WebSocket 异常: %s", e, exc_info=True)
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

