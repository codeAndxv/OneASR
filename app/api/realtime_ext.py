"""扩展版 Realtime Transcription — 兼容 OpenAI 协议 + OneASR 扩展字段。

路由: WS /v1/realtimeext

扩展特性:
- language（单语言字符串，而非 languages 数组）
- heartbeat 心跳事件（每 5 秒）
- buffer delta（未 commit 的中间文本推送）
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

logger = logging.getLogger(__name__)

router = APIRouter(tags=["realtimeext"])


@router.websocket("/v1/realtimeext")
async def realtime_transcription_ext(ws: WebSocket):
    """扩展版 WebSocket 实时转录接口。"""
    try:
        await ws.accept()
    except Exception as e:
        logger.warning("[realtimeext] 接受 WebSocket 连接失败: %s", e)
        return

    if not verify_ws_api_key(ws):
        try:
            await ws.send_json({"type": "error", "error": {"code": "invalid_api_key", "message": "API Key 无效"}})
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
            await _send_error("engine_error", f"引擎加载失败: {e}")
            return

        # ── X-ASR 原生流式模式 ──
        if hasattr(eng, "create_stream_session"):
            from app.api.realtime import _xasr_session
            await _xasr_session(ws, eng, session, _send_event, _send_error)
            return

        try:
            processor = await asyncio.to_thread(eng.create_audio_processor, language=session.language, pcm_input=True)
        except Exception as e:
            await _send_error("processor_error", f"创建 AudioProcessor 失败: {e}")
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
        """从 AudioProcessor 读取转录结果，发送 delta/completed 事件。"""
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

                # 已确认的行：发送 delta + completed
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

                # 扩展：发送缓冲文本变化（未 commit 的中间文本）
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
                await _send_error("invalid_message", "无法解析 JSON 消息")
                continue

            event_type = event.get("type")

            if event_type == "session.update":
                await _handle_session_update(event)

            elif event_type == "input_audio_buffer.append":
                if processor is None:
                    await _send_error("invalid_state", "请先发送 session.update 配置会话")
                    continue

                audio_b64 = event.get("audio", "")
                if not audio_b64:
                    continue

                try:
                    audio_bytes = base64.b64decode(audio_b64)
                except Exception:
                    await _send_error("invalid_audio", "无法解码 base64 音频数据")
                    continue

                if session.state == SessionState.CONFIGURED:
                    session.state = SessionState.LISTENING

                await processor.process_audio(audio_bytes)

            elif event_type == "input_audio_buffer.commit":
                if processor is None or session.state != SessionState.LISTENING:
                    await _send_error("invalid_state", "没有活跃的转录会话")
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
