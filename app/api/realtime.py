"""OpenAI Realtime Transcription 风格的 WebSocket 流式语音识别接口。

严格遵循 OpenAI Realtime 官方规范：
1. 握手认证成功后首先主动发送 session.created 事件
2. session.update 成功后返回标准 session.updated 事件
3. 仅发送官方标准事件（不包含 heartbeat、done 等扩展字段或非标事件）
4. delta 事件仅包含 type, item_id, content_index, delta
5. 支持多采样率音频输入，在引擎层自动完成采样率重采样对齐
6. 统一的 session 级转录记录持久化（save_streaming_record）

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
from app.utils.audio_converter import AudioConverter

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
        self.languages: list[str] = []
        self.model: str | None = None
        self.delay: str | None = None
        self.input_sample_rate: int = 24000
        self.item_counter = 0
        self.transcript_parts: list[str] = []

    def next_item_id(self) -> str:
        self.item_counter += 1
        return f"item_{self.session_id[:8]}_{self.item_counter}"


# 句末强标点与弱标点定义
STRONG_PUNCTUATIONS = ("。", "？", "！", ".", "?", "!")
WEAK_PUNCTUATIONS = ("，", "；", "、", ",", ";")
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
    """判定当前流式识别是否到达语义或标点断句点。"""
    cleaned = clean_dangling_punct(full_text).strip()
    if not cleaned:
        return False, "empty"

    if is_acoustic_endpoint:
        return True, "acoustic_silence"

    trailing = cleaned.rstrip(" \"'”’")
    if not trailing:
        return False, "empty"
    last_char = trailing[-1]

    if duration >= min_sentence_duration and last_char in STRONG_PUNCTUATIONS:
        return True, "strong_punctuation"

    if (duration >= target_clause_duration or len(cleaned) >= 16) and last_char in WEAK_PUNCTUATIONS:
        return True, "clause_punctuation"

    if duration >= max_sentence_duration:
        return True, "max_duration_ceiling"

    return False, "none"


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
    """X-ASR 原生流式识别会话（支持标点与语义动态软断句）。"""
    stream_session = eng.create_stream_session(input_sample_rate=session.input_sample_rate)

    session.state = SessionState.CONFIGURED
    sample_rate = session.input_sample_rate or 16000
    total_samples = 0
    last_sentence_end_time = 0.0
    current_sentence_has_emitted_delta = False

    logger.info(
        "[realtime-xasr] 启动 X-ASR 会话: session_id=%s, model=%s, language=%s, rate=%d",
        session.session_id, session.model or "xasr", session.language, session.input_sample_rate,
    )

    # 发送 session.updated 确认
    await send_event({
        "type": "session.updated",
        "session": {
            "id": session.session_id,
            "type": "transcription",
            "audio": {
                "input": {
                    "format": {"type": "audio/pcm", "rate": session.input_sample_rate},
                    "transcription": {
                        "model": session.model or "xasr",
                        "language": session.language,
                        "languages": session.languages,
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
                    logger.info("[realtime-xasr] 开始接收并解码音频流: session_id=%s", session.session_id)

                # 送入 sherpa-onnx 识别（引擎层自动完成采样率重采样）
                stream_session.accept_audio(audio_bytes, input_sample_rate=session.input_sample_rate)
                stream_session.decode()

                # 发送 partial 增量结果（标准格式，无多余字段）
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
                        })

                # 标点与语义动态软断句判定
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
                            "[realtime-xasr] 识别完成语句 (触发原因: %s): %s (session_id=%s)",
                            reason, clean_text, session.session_id,
                        )
                        await send_event({
                            "type": "conversation.item.input_audio_transcription.completed",
                            "item_id": item_id,
                            "content_index": 0,
                            "transcript": clean_text,
                        })
                        last_sentence_end_time = current_time
                        current_sentence_has_emitted_delta = False

                    stream_session.reset_endpoint()

            elif event_type == "input_audio_buffer.commit":
                if session.state != SessionState.LISTENING:
                    await send_error("invalid_state", "No active transcription session")
                    continue

                session.state = SessionState.FINALIZING

                # 获取最终结果
                raw_final = stream_session.finalize()
                final_text = clean_dangling_punct(raw_final).strip()
                if final_text:
                    session.transcript_parts.append(final_text)
                    item_id = session.next_item_id()
                    logger.info(
                        "[realtime-xasr] 提交 commit 最终尾句: '%s' (session_id=%s)",
                        final_text, session.session_id,
                    )
                    await send_event({
                        "type": "conversation.item.input_audio_transcription.completed",
                        "item_id": item_id,
                        "content_index": 0,
                        "transcript": final_text,
                    })

                logger.info(
                    "[realtime-xasr] 会话 turn 结束: session_id=%s, 总句数=%d",
                    session.session_id, len(session.transcript_parts),
                )
                # 恢复为 CONFIGURED 状态，等待后续音频 turn 或关闭连接
                session.state = SessionState.CONFIGURED

            elif event_type == "session.update":
                pass  # 已配置，忽略重复更新

            else:
                logger.debug("[realtime-xasr] 未知事件类型: %s", event_type)

    except WebSocketDisconnect:
        logger.info("[realtime-xasr] 客户端断开连接: session_id=%s", session.session_id)
    except Exception as e:
        if "close message has been sent" in str(e):
            logger.info("[realtime-xasr] 连接正常关闭: session_id=%s", session.session_id)
        else:
            logger.error("[realtime-xasr] 会话异常: %s", e, exc_info=True)
            await send_error("session_error", str(e))


# ═══════════════════════════════════════════════════════════════════
#  主端点
# ═══════════════════════════════════════════════════════════════════

@router.websocket("/v1/realtime")
async def realtime_transcription(ws: WebSocket):
    """OpenAI Realtime Transcription 风格的标准 WebSocket 接口。"""
    try:
        await ws.accept()
    except Exception as e:
        logger.warning("接受 WebSocket 连接失败: %s", e)
        return

    if not verify_ws_api_key(ws):
        logger.warning("[realtime] WebSocket 鉴权失败: client=%s", ws.client)
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
    t_start = time.time()
    record_id = str(uuid.uuid4())

    logger.info(
        "[realtime] WebSocket 连接已建立: client=%s, session_id=%s, record_id=%s",
        ws.client, session.session_id, record_id,
    )

    async def _send_event(event: dict):
        try:
            await ws.send_json(event)
        except Exception:
            pass

    async def _send_error(code: str, message: str):
        await _send_event({"type": "error", "error": {"code": code, "message": message}})

    # 1. 握手成功后，立即下发标准 session.created 事件
    await _send_event({
        "type": "session.created",
        "session": {
            "id": session.session_id,
            "type": "transcription",
            "audio": {
                "input": {
                    "format": {"type": "audio/pcm", "rate": session.input_sample_rate},
                    "transcription": {
                        "model": "gpt-live-transcribe",
                    },
                },
            },
        },
    })

    async def _handle_session_update(data: dict):
        nonlocal processor, eng, results_task
        sess_cfg = data.get("session", {})

        audio_input = sess_cfg.get("audio", {}).get("input", {})
        format_cfg = audio_input.get("format", {})
        transcription_cfg = audio_input.get("transcription", {})

        session.language = transcription_cfg.get("language")
        session.languages = transcription_cfg.get("languages") or ([] if not session.language else [session.language])
        session.model = transcription_cfg.get("model")
        session.delay = transcription_cfg.get("delay")
        session.input_sample_rate = format_cfg.get("rate") or 24000

        logger.info(
            "[realtime] 收到 session.update 配置: session_id=%s, model=%s, language=%s, rate=%d, delay=%s",
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

        await _send_event({
            "type": "session.updated",
            "session": {
                "id": session.session_id,
                "type": "transcription",
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": session.input_sample_rate},
                        "transcription": {
                            "model": session.model or "whisper1",
                            "language": session.language,
                            "languages": session.languages,
                            "delay": session.delay,
                        },
                    },
                },
            },
        })

    async def _forward_results(_ignored_gen):
        """直接从 AudioProcessor 读取状态（标准 delta/completed 事件推送）。"""
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
                    logger.info("[realtime-whisper] 识别完成语句: %s (session_id=%s)", text, session.session_id)
                    await _send_event({
                        "type": "conversation.item.input_audio_transcription.delta",
                        "item_id": item_id,
                        "content_index": 0,
                        "delta": text,
                    })
                    session.transcript_parts.append(text)
                    await _send_event({
                        "type": "conversation.item.input_audio_transcription.completed",
                        "item_id": item_id,
                        "content_index": 0,
                        "transcript": text,
                    })

                if buffer_text != last_buffer:
                    if buffer_text:
                        item_id = session.next_item_id()
                        await _send_event({
                            "type": "conversation.item.input_audio_transcription.delta",
                            "item_id": item_id,
                            "content_index": 0,
                            "delta": buffer_text,
                        })
                    last_buffer = buffer_text

                await asyncio.sleep(0.1)

        except WebSocketDisconnect:
            pass
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception("Realtime 结果处理异常: %s", e)

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
                # X-ASR 模式下 _handle_session_update 已经处理完整个会话周期，退出主循环进入 finally
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

                # 本地处理器若采样率不同，通过 AudioConverter 进行重采样
                proc_sr = getattr(processor, "sample_rate", 16000) or 16000
                if session.input_sample_rate != proc_sr:
                    audio_bytes = AudioConverter.resample_pcm16(audio_bytes, session.input_sample_rate, proc_sr)

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

                session.state = SessionState.CONFIGURED

            else:
                logger.debug("未知事件类型: %s", event_type)

    except WebSocketDisconnect:
        logger.info("Realtime 客户端断开连接: session_id=%s", session.session_id)
    except Exception as e:
        logger.error("Realtime WebSocket 异常: %s", e, exc_info=True)
    finally:
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

        eng_model = eng.model_name if (eng and hasattr(eng, "model_name")) else None
        total_time = time.time() - t_start
        logger.info(
            "[realtime] 会话关闭释放: session_id=%s, model=%s, 识别总句数=%d, 总耗时=%.2fs",
            session.session_id, session.model or "unknown", len(session.transcript_parts), total_time,
        )
        await save_streaming_record(
            record_id=record_id,
            engine_name=session.model or "whisper1",
            model_name=eng_model,
            language=session.language,
            line_count=len(session.transcript_parts),
            total_time=total_time,
            is_completed=session.state in (SessionState.FINALIZING, SessionState.CONFIGURED),
        )
