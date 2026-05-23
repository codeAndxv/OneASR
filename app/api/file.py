from fastapi import APIRouter, File, UploadFile, HTTPException

from app.engines.registry import get_engine
from app.models.schemas import FileRequest, FileResponse
from app.utils.download import download_url

router = APIRouter(prefix="/api/v1", tags=["file"])


@router.post("/transcribe/file", response_model=FileResponse)
async def transcribe_file(
    file: UploadFile = File(...),
    engine: str | None = None,
):
    """上传音视频文件进行识别。"""
    data = await file.read()
    eng = get_engine(engine)
    text, segments = await eng.transcribe_file(data)
    return FileResponse(text=text, segments=segments, engine=eng.__class__.__name__)


@router.post("/transcribe/url", response_model=FileResponse)
async def transcribe_url(req: FileRequest):
    """通过 URL 下载音视频文件进行识别。"""
    try:
        path = await download_url(str(req.url))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    data = path.read_bytes()
    eng = get_engine(req.engine)
    text, segments = await eng.transcribe_file(data)
    return FileResponse(text=text, segments=segments, engine=eng.__class__.__name__)
