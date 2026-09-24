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


# 句末强标点符号集合（句号、问号、叹号）
STRONG_PUNCTUATIONS = ("。", "？", "！", ".", "?", "!")
# 停顿/分句弱标点符号集合（逗号、分号、顿号）
WEAK_PUNCTUATIONS = ("，", "；", "、", ",", ";")
# 句首悬挂残留标点与空白集合（用于清洗切句后下一句开头误带出的标点）
DANGLING_PUNCTUATIONS = " \t\n\r，,。、；;：:？！?!…—"


def clean_dangling_punct(text: str) -> str:
    """去除句子开头悬挂的前句残留标点和空白。"""
    if not text:
        return ""
    return text.lstrip(DANGLING_PUNCTUATIONS)


def evaluate_soft_endpoint(
    full_text: str,
    duration: float,
    is_acoustic_endpoint: bool,
    min_sentence_duration: float = 1.5,
    target_clause_duration: float = 4.0,
    max_sentence_duration: float = 8.0,
) -> tuple[bool, str]:
    """判定当前流式识别是否到达语义或标点断句点。

    Args:
        full_text: 当前流式识别器输出的累计文本
        duration: 当前正在识别的句子已持续的时长（秒）
        is_acoustic_endpoint: sherpa 底层声学静音检测是否已触发

    Returns:
        (should_endpoint, reason)
    """
    cleaned = clean_dangling_punct(full_text).strip()
    if not cleaned:
        return False, "empty"

    # 1. 物理声学静音端点（Sherpa 尾部静音）
    if is_acoustic_endpoint:
        return True, "acoustic_silence"

    trailing = cleaned.rstrip(" \"'”’")
    if not trailing:
        return False, "empty"
    last_char = trailing[-1]

    # 2. 句末强标点 (。？！.?!)：达到基础时长 (>= 1.5s) 时即刻断句
    if duration >= min_sentence_duration and last_char in STRONG_PUNCTUATIONS:
        return True, "strong_punctuation"

    # 3. 分句弱标点 (，；、,;)：单句达到目标时长 (>= 4.0s) 或字数较多 (>= 16 字) 时顺势断句
    if (duration >= target_clause_duration or len(cleaned) >= 16) and last_char in WEAK_PUNCTUATIONS:
        return True, "clause_punctuation"

    # 4. 超长上限硬保护 (>= 8.0s)：防止极端情况下连续说话无标点导致字幕过长
    if duration >= max_sentence_duration:
        return True, "max_duration_ceiling"

    return False, "none"


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
    """X-ASR 原生流式扩展识别会话（支持标点与语义动态软断句）。"""
    input_sr = getattr(session, "input_sample_rate", 16000) or 16000
    stream_session = eng.create_stream_session(input_sample_rate=input_sr)
    session.state = SessionState.CONFIGURED

    sample_rate = input_sr
    total_samples = 0
    last_sentence_end_time = 0.0
    current_sentence_has_emitted_delta = False

    logger.info(
        "[realtimeext-xasr] 启动 X-ASR 原生流式会话: session_id=%s, model=%s, language=%s, input_sr=%d",
        session.session_id, session.model or "xasr", session.language, input_sr,
    )

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
                current_sentence_duration = max(0.0, current_time - last_sentence_end_time)

                if session.state == SessionState.CONFIGURED:
                    session.state = SessionState.LISTENING
                    logger.info("[realtimeext-xasr] 开始接收并解码音频流: session_id=%s", session.session_id)

                stream_session.accept_audio(audio_bytes, input_sample_rate=sample_rate)
                stream_session.decode()

                # 1. 获取并发送 partial 增量结果（自动过滤句首残留标点）
                raw_partial = stream_session.get_partial_result()
                if raw_partial:
                    partial = raw_partial
                    if not current_sentence_has_emitted_delta:
                        partial = clean_dangling_punct(raw_partial)

                    if partial:
                        current_sentence_has_emitted_delta = True
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

                # 2. 标点与语义动态软断句判定
                raw_full = stream_session.get_full_text()
                is_acoustic = stream_session.is_endpoint()
                should_endpoint, reason = evaluate_soft_endpoint(
                    full_text=raw_full,
                    duration=current_sentence_duration,
                    is_acoustic_endpoint=is_acoustic,
                )

                if should_endpoint:
                    clean_text = clean_dangling_punct(raw_full).strip()
                    if clean_text:
                        session.transcript_parts.append(clean_text)
                        item_id = session.next_item_id()
                        logger.info(
                            "[realtimeext-xasr] 识别完成语句 [%.2fs - %.2fs] (触发原因: %s): %s (session_id=%s)",
                            last_sentence_end_time, current_time, reason, clean_text, session.session_id,
                        )
                        # 扩展事件：sentence（携带整句完整文本与精准时间戳）
                        await send_event({
                            "type": "conversation.item.input_audio_transcription.sentence",
                            "item_id": item_id,
                            "content_index": 0,
                            "text": clean_text,
                            "transcript": clean_text,
                            "start": round(last_sentence_end_time, 2),
                            "end": round(current_time, 2),
                            "is_endpoint": True,
                        })
                        # 兼容事件：completed
                        await send_event({
                            "type": "conversation.item.input_audio_transcription.completed",
                            "item_id": item_id,
                            "content_index": 0,
                            "transcript": clean_text,
                            "start": round(last_sentence_end_time, 2),
                            "end": round(current_time, 2),
                            "is_endpoint": True,
                        })
                        last_sentence_end_time = current_time
                        current_sentence_has_emitted_delta = False

                    # 重置 stream 状态以便进行下一句识别
                    stream_session.reset_endpoint()

            elif event_type == "input_audio_buffer.commit":
                if session.state != SessionState.LISTENING:
                    await send_error("invalid_state", "No active transcription session")
                    continue

                session.state = SessionState.FINALIZING
                raw_final = stream_session.finalize()
                final_text = clean_dangling_punct(raw_final).strip()
                current_time = total_samples / sample_rate
                if final_text:
                    session.transcript_parts.append(final_text)
                    item_id = session.next_item_id()
                    logger.info(
                        "[realtimeext-xasr] 最终尾句定稿 [%.2fs - %.2fs]: %s (session_id=%s)",
                        last_sentence_end_time, current_time, final_text, session.session_id,
                    )
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

                logger.info(
                    "[realtimeext-xasr] 提交 commit: session_id=%s, 音频总时长=%.2fs, 总句数=%d",
                    session.session_id, total_samples / sample_rate, len(session.transcript_parts),
                )
                await send_event({"type": "done"})
                try:
                    await ws.close()
                except Exception:
                    pass
                return

            elif event_type == "session.update":
                pass

            else:
                logger.debug("[realtimeext-xasr] 未知事件类型: %s", event_type)

    except WebSocketDisconnect:
        logger.info("[realtimeext-xasr] 客户端断开连接: session_id=%s", session.session_id)
    except Exception as e:
        if "close message has been sent" in str(e):
            logger.info("[realtimeext-xasr] 连接正常关闭: session_id=%s", session.session_id)
        else:
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
        logger.warning("[realtimeext] WebSocket 鉴权失败: client=%s", ws.client)
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

    logger.info(
        "[realtimeext] WebSocket 连接已建立: client=%s, session_id=%s, record_id=%s",
        ws.client, session.session_id, record_id,
    )

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
        session.input_sample_rate = format_cfg.get("rate") or 16000

        logger.info(
            "[realtimeext] 收到 session.update 配置: session_id=%s, model=%s, language=%s, rate=%d, delay=%s",
            session.session_id, session.model, session.language, session.input_sample_rate, session.delay,
        )

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
                    logger.info(
                        "[realtimeext-whisper] 识别完成语句 [%.2fs - %.2fs]: %s (session_id=%s)",
                        round(line_start, 2), round(line_end, 2), text, session.session_id,
                    )

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
                try:
                    await ws.close()
                except Exception:
                    pass
                return

            else:
                logger.debug("[realtimeext] 未知事件类型: %s", event_type)

    except WebSocketDisconnect:
        logger.info("[realtimeext] 客户端断开连接: session_id=%s", session.session_id)
    except Exception as e:
        if "close message has been sent" in str(e):
            logger.info("[realtimeext] 连接正常关闭: session_id=%s", session.session_id)
        else:
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
        total_time = time.time() - t_start
        logger.info(
            "[realtimeext] 会话关闭释放: session_id=%s, model=%s, 识别总句数=%d, 总耗时=%.2fs",
            session.session_id, session.model or "unknown", len(session.transcript_parts), total_time,
        )
        await save_streaming_record(
            record_id=record_id,
            engine_name=session.model or "whisper1",
            model_name=eng_model,
            language=session.language,
            line_count=len(session.transcript_parts),
            total_time=total_time,
            is_completed=session.state == SessionState.FINALIZING,
        )

