from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import PlainTextResponse

from app.core.config import app_config
from app.engines.registry import get_engine
from app.models.schemas import FileRequest, FileResponse, OutputFormat
from app.utils.download import download_url
from app.utils.format import format_output

router = APIRouter(prefix="/api/v1", tags=["file"])


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
    engine: str | None = None,
    format: OutputFormat = OutputFormat.TEXT,
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
