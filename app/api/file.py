import json
import logging

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from fastapi.responses import PlainTextResponse, StreamingResponse

from app.api.auth import get_api_key

logger = logging.getLogger(__name__)
from app.core.config import app_config
from app.engines.registry import get_engine
from app.models.schemas import FileRequest, FileResponse, OutputFormat
from app.utils.download import download_url
from app.utils.format import format_output

router = APIRouter(prefix="/api/v1", tags=["file"], dependencies=[Depends(get_api_key)])


@router.get("/engines")
async def list_engines():
    """列出所有可用的 ASR 引擎。"""
    engines = []
    for name, config in app_config.engines.items():
        engines.append({
            "name": name,
            "type": config.type,
            "model_name": config.model_name,
            "model_path": str(config.model_path),
        })
    return {"default": app_config.default_engine, "engines": engines}


@router.get("/formats")
async def list_formats():
    """列出所有支持的输出格式。"""
    return {
        "formats": [
            {"name": "text", "description": "纯文本"},
            {"name": "srt", "description": "SRT 字幕格式"},
            {"name": "vtt", "description": "WebVTT 字幕格式"},
            {"name": "json", "description": "JSON 格式（含时间轴）"},
            {"name": "tsv", "description": "TSV 格式（制表符分隔）"},
        ]
    }


@router.post("/transcribe/file")
async def transcribe_file(
    file: UploadFile = File(...),
    engine: str | None = Form(None),
    format: OutputFormat = Form(OutputFormat.TEXT),
):
    """上传音视频文件进行识别。

    - **file**: 音视频文件
    - **engine**: 引擎名称（如 whisper、firered）
    - **format**: 输出格式（text/srt/vtt/json/tsv）
    """
    data = await file.read()
    eng = get_engine(engine)
    text, segments = await eng.transcribe_file(data)

    if format == OutputFormat.JSON:
        return PlainTextResponse(
            format_output(text, segments, format),
            media_type="application/json",
        )
    elif format == OutputFormat.TEXT:
        return PlainTextResponse(text, media_type="text/plain")
    else:
        return PlainTextResponse(
            format_output(text, segments, format),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename=transcript.{format.value}"},
        )


@router.post("/transcribe/url")
async def transcribe_url(req: FileRequest):
    """通过 URL 下载音视频文件进行识别。

    - **url**: 音视频 URL
    - **engine**: 引擎名称（如 whisper、firered）
    - **format**: 输出格式（text/srt/vtt/json/tsv）
    """
    try:
        path = await download_url(str(req.url))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    data = path.read_bytes()
    eng = get_engine(req.engine)
    text, segments = await eng.transcribe_file(data)

    if req.format == OutputFormat.JSON:
        return PlainTextResponse(
            format_output(text, segments, req.format),
            media_type="application/json",
        )
    elif req.format == OutputFormat.TEXT:
        return PlainTextResponse(text, media_type="text/plain")
    else:
        return PlainTextResponse(
            format_output(text, segments, req.format),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename=transcript.{req.format.value}"},
        )


async def _stream_sse(eng, data: bytes):
    """SSE 生成器：逐句推送识别结果。"""
    idx = 0
    try:
        async for seg in eng.transcribe_file_stream(data):
            event = {"index": idx, "start": seg.start, "end": seg.end, "text": seg.text}
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            idx += 1
        yield "data: {\"done\": true}\n\n"
    except (ConnectionResetError, BrokenPipeError, OSError) as e:
        logger.info("SSE 流客户端已断开: %s", e)
    except Exception as e:
        logger.exception("SSE 流异常: %s", e)
        yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"


@router.post("/transcribe/file/stream")
async def transcribe_file_stream(
    file: UploadFile = File(...),
    engine: str | None = Form(None),
):
    """上传音视频文件，以 SSE 流式返回每句识别结果。

    每个 SSE 事件格式: `data: {"index": N, "start": 0.0, "end": 1.5, "text": "..."}`
    结束标志: `data: {"done": true}`

    - **file**: 音视频文件
    - **engine**: 引擎名称（如 whisper、firered）
    """
    data = await file.read()
    eng = get_engine(engine)
    return StreamingResponse(
        _stream_sse(eng, data),
        media_type="text/event-stream",
    )


@router.post("/transcribe/url/stream")
async def transcribe_url_stream(
    req: FileRequest,
):
    """通过 URL 下载音视频文件，以 SSE 流式返回每句识别结果。

    每个 SSE 事件格式: `data: {"index": N, "start": 0.0, "end": 1.5, "text": "..."}`
    结束标志: `data: {"done": true}`

    - **url**: 音视频 URL
    - **engine**: 引擎名称（如 whisper、firered）
    """
    try:
        path = await download_url(str(req.url))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    data = path.read_bytes()
    eng = get_engine(req.engine)
    return StreamingResponse(
        _stream_sse(eng, data),
        media_type="text/event-stream",
    )
