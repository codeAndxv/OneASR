from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.engines.registry import get_engine
from app.models.schemas import StreamResponse

router = APIRouter(tags=["stream"])


@router.websocket("/ws/transcribe/stream")
async def transcribe_stream(ws: WebSocket, engine: str | None = None):
    """WebSocket 流式识别。

    客户端持续发送二进制音频帧，服务端返回 JSON 格式的中间/最终结果。
    客户端发送文本 "end" 表示流结束。
    """
    await ws.accept()
    eng = get_engine(engine)

    try:
        while True:
            msg = await ws.receive()

            if "text" in msg and msg["text"] == "end":
                final_text = await eng.stream_finalize()
                await ws.send_json(StreamResponse(text=final_text, is_final=True).model_dump())
                break

            chunk = msg.get("bytes")
            if chunk:
                partial = await eng.transcribe_stream(chunk)
                if partial:
                    await ws.send_json(
                        StreamResponse(text=partial, is_final=False).model_dump()
                    )

    except WebSocketDisconnect:
        pass
