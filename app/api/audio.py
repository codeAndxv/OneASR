"""统一的语音识别 API 接口（参考 OpenAI 格式）。"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse, StreamingResponse

from app.api.auth import get_api_key
from app.core.config import app_config
from app.engines.registry import get_engine
from app.models.schemas import (
    OutputFormat,
    Segment,
    TranscriptionRequest,
    TranscriptionResponse,
)
from app.utils.download import download_url
from app.utils.format import format_output

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/audio", tags=["audio"], dependencies=[Depends(get_api_key)])


@router.get("/models")
async def list_models():
    """列出所有可用的 ASR 模型（兼容 OpenAI 格式）。"""
    models = []
    for name, config in app_config.engines.items():
        models.append({
            "id": name,
            "object": "model",
            "owned_by": "local",
            "type": config.type,
            "model_name": config.model_name,
        })
    return {
        "object": "list",
        "data": models,
    }


@router.post("/transcriptions", response_model=TranscriptionResponse)
async def create_transcription(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    response_format: OutputFormat = Form(OutputFormat.JSON),
    prompt: Optional[str] = Form(None),
):
    """创建语音识别任务（兼容 OpenAI 格式）。

    支持两种方式：
    1. 上传文件：使用 file 参数
    2. URL 识别：使用 url 参数

    请求格式：
    - Content-Type: multipart/form-data
    - file: 音视频文件（与 url 二选一）
    - url: 音视频 URL（与 file 二选一）
    - model: 引擎名称（如 faster-whisper、wlk）
    - language: 语言代码（可选，如 zh、en、auto）
    - response_format: 输出格式（json、text、srt、vtt、tsv）
    """
    # 验证参数
    if not file and not url:
        raise HTTPException(status_code=400, detail="必须提供 file 或 url 参数")

    try:
        # 获取音频数据
        if file:
            data = await file.read()
        else:
            try:
                path = await download_url(url)
                data = path.read_bytes()
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"下载 URL 失败: {e}")

        # 获取引擎并识别
        eng = get_engine(model)
        text, segments = await eng.transcribe_file(data)

        # 构建响应
        response = TranscriptionResponse(
            text=text,
            segments=[
                Segment(id=i, start=seg.start, end=seg.end, text=seg.text)
                for i, seg in enumerate(segments)
            ],
            engine=model or app_config.default_engine,
        )

        # 根据格式返回
        if response_format == OutputFormat.JSON:
            return response
        elif response_format == OutputFormat.TEXT:
            return PlainTextResponse(text, media_type="text/plain")
        else:
            return PlainTextResponse(
                format_output(text, segments, response_format),
                media_type="text/plain",
                headers={"Content-Disposition": f"attachment; filename=transcript.{response_format.value}"},
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("语音识别失败: %s", e)
        raise HTTPException(status_code=500, detail=f"识别失败: {e}")


@router.post("/transcriptions/stream")
async def create_transcription_stream(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
):
    """创建流式语音识别任务。

    以 SSE 格式逐句返回识别结果。

    请求格式：
    - Content-Type: multipart/form-data
    - file: 音视频文件（与 url 二选一）
    - url: 音视频 URL（与 file 二选一）
    - model: 引擎名称（如 faster-whisper、wlk）
    - language: 语言代码（可选）

    响应格式（SSE）：
    - data: {"index": 0, "start": 0.0, "end": 2.5, "text": "Hello"}
    - data: {"done": true}
    """
    # 验证参数
    if not file and not url:
        raise HTTPException(status_code=400, detail="必须提供 file 或 url 参数")

    try:
        # 获取音频数据
        if file:
            data = await file.read()
        else:
            try:
                path = await download_url(url)
                data = path.read_bytes()
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"下载 URL 失败: {e}")

        # 获取引擎
        eng = get_engine(model)

        # 返回 SSE 流
        async def stream_generator():
            idx = 0
            try:
                async for seg in eng.transcribe_file_stream(data):
                    event = {"index": idx, "start": seg.start, "end": seg.end, "text": seg.text}
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    idx += 1
                yield 'data: {"done": true}\n\n'
            except (ConnectionResetError, BrokenPipeError, OSError) as e:
                logger.info("SSE 流客户端已断开: %s", e)
            except Exception as e:
                logger.exception("SSE 流异常: %s", e)
                yield f'data: {json.dumps({"error": str(e)}, ensure_ascii=False)}\n\n'

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("流式识别失败: %s", e)
        raise HTTPException(status_code=500, detail=f"识别失败: {e}")


@router.get("/transcriptions/{transcription_id}")
async def get_transcription(transcription_id: str):
    """获取语音识别任务状态（兼容 OpenAI 格式，暂未实现）。

    用于查询异步识别任务的状态和结果。
    """
    raise HTTPException(status_code=501, detail="异步任务功能暂未实现")


@router.delete("/transcriptions/{transcription_id}")
async def delete_transcription(transcription_id: str):
    """删除语音识别任务（兼容 OpenAI 格式，暂未实现）。

    用于取消或删除异步识别任务。
    """
    raise HTTPException(status_code=501, detail="异步任务功能暂未实现")
