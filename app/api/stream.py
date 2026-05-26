import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.auth import verify_ws_api_key
from app.engines.registry import get_engine
from app.engines.wlk_engine import WLKEngine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stream"])


async def _handle_results(websocket: WebSocket, results_generator):
    """消费 AudioProcessor 的结果并通过 WebSocket 发送。"""
    try:
        async for response in results_generator:
            await websocket.send_json(response.to_dict())
        await websocket.send_json({"type": "ready_to_stop"})
    except WebSocketDisconnect:
        logger.info("客户端在结果处理期间断开连接")
    except Exception as e:
        logger.exception("结果处理异常: %s", e)


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
    # 验证 API Key
    if not verify_ws_api_key(ws):
        await ws.accept()
        await ws.send_json({"type": "error", "error": "API Key 无效"})
        await ws.close()
        return

    eng = get_engine(engine)

    if not isinstance(eng, WLKEngine):
        await ws.accept()
        await ws.send_json({
            "type": "error",
            "error": f"引擎 '{engine or '默认'}' 不支持流式识别，请使用 wlk 引擎",
        })
        await ws.close()
        return

    # 先接受连接，避免模型加载期间客户端超时
    await ws.accept()
    logger.info("WebSocket 流式识别已连接%s", f" language={language}" if language else "")

    # 在线程中创建 AudioProcessor（可能触发 ASR 模型加载，会阻塞）
    processor = await asyncio.to_thread(eng.create_audio_processor, language)

    # 发送配置信息
    await ws.send_json({
        "type": "config",
        "useAudioWorklet": processor.is_pcm_input,
        "mode": "full",
    })

    # 启动处理管道，获取结果生成器
    results_generator = await processor.create_tasks()
    results_task = asyncio.create_task(_handle_results(ws, results_generator))

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
