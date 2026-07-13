"""WebSocket 流式语音识别 API（基于 WhisperLiveKit）。"""

import asyncio
import logging
import time
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.auth import verify_ws_api_key
from app.engines.registry import get_engine
from app.engines.whisperlivekit_engine import WhisperLiveKitEngine
from app.services.record_service import save_streaming_record

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stream"])


@router.websocket("/ws/transcribe/stream")
async def transcribe_stream(ws: WebSocket, engine: str | None = None, language: str | None = None):
    """WebSocket 流式识别（基于 WhisperLiveKit）。

    客户端持续发送二进制音频帧，服务端返回 JSON 格式的识别结果。
    发送空字节 (b"") 表示流结束。

    查询参数:
        engine: 引擎名称，默认使用配置的默认引擎
        language: 语言覆盖（如 zh、en、auto）

    响应格式:
        {
            "status": "active_transcription",
            "lines": [{"speaker": 1, "text": "...", "start": "0:00:05.30", "end": "0:00:08.10"}],
            "buffer_transcription": "部分文本...",
            "buffer_diarization": "",
            "buffer_translation": ""
        }
    """
    # ── 建立连接 ───────────────────────────────────────────────
    try:
        await ws.accept()
    except Exception as e:
        logger.warning("接受 WebSocket 连接失败: %s", e)
        return

    if not verify_ws_api_key(ws):
        try:
            await ws.send_json({"type": "error", "error": "API Key 无效"})
            await ws.close()
        except Exception:
            pass
        return

    # ── 获取引擎 ───────────────────────────────────────────────
    try:
        eng = get_engine(engine)
    except Exception as e:
        logger.error("获取引擎失败: %s", e)
        try:
            await ws.send_json({"type": "error", "error": f"引擎加载失败: {e}"})
            await ws.close()
        except Exception:
            pass
        return

    if not isinstance(eng, WhisperLiveKitEngine):
        error_msg = f"引擎 '{engine or '默认'}' 不支持流式识别，请使用 whisperlivekit 引擎"
        logger.warning(error_msg)
        try:
            await ws.send_json({"type": "error", "error": error_msg})
            await ws.close()
        except Exception:
            pass
        return

    # ── 初始化 ─────────────────────────────────────────────────
    record_id = str(uuid.uuid4())
    t_start = time.time()
    line_count = 0

    logger.info("WebSocket 流式识别已连接%s", f" language={language}" if language else "")

    processor = await asyncio.to_thread(eng.create_audio_processor, language)

    await ws.send_json({
        "type": "config",
        "useAudioWorklet": processor.is_pcm_input,
        "mode": "full",
    })

    results_generator = await processor.create_tasks()

    # ── 结果转发 + 计数 ────────────────────────────────────────
    async def _forward_results(gen):
        nonlocal line_count
        try:
            async for response in gen:
                await ws.send_json(response.to_dict())
                if hasattr(response, "lines") and response.lines:
                    line_count = max(line_count, len(response.lines))
            await ws.send_json({"type": "ready_to_stop"})
        except WebSocketDisconnect:
            logger.info("客户端在结果处理期间断开连接")
        except Exception as e:
            logger.exception("结果处理异常: %s", e)

    results_task = asyncio.create_task(_forward_results(results_generator))

    # ── 接收音频帧 ─────────────────────────────────────────────
    try:
        while True:
            message = await ws.receive_bytes()
            await processor.process_audio(message)
    except KeyError as e:
        if "bytes" in str(e):
            logger.info("客户端已关闭连接")
        else:
            logger.error("WebSocket 接收异常: %s", e, exc_info=True)
    except WebSocketDisconnect:
        logger.info("客户端断开 WebSocket 连接")
    except Exception as e:
        logger.error("WebSocket 异常: %s", e, exc_info=True)
    finally:
        # ── 清理 ───────────────────────────────────────────────
        logger.info("清理 WebSocket 流式识别资源...")
        if not results_task.done():
            results_task.cancel()
        try:
            await results_task
        except asyncio.CancelledError:
            logger.info("结果处理任务已取消")
        except Exception as e:
            logger.warning("结果处理任务异常: %s", e)

        await processor.cleanup()
        logger.info("WebSocket 流式识别资源清理完成")

        # ── 持久化记录 ─────────────────────────────────────────
        eng_model = eng.model_name if hasattr(eng, "model_name") else None
        await save_streaming_record(
            record_id=record_id,
            engine_name=engine or "whisperlivekit",
            model_name=eng_model,
            language=language,
            line_count=line_count,
            total_time=time.time() - t_start,
            is_completed=True,
        )
