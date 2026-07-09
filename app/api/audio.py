"""统一的语音识别 API 接口（参考 OpenAI 格式）。"""

import json
import logging
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse, StreamingResponse

from app.api.auth import get_api_key
from app.core.config import app_config
from app.core.file_storage import file_storage
from app.engines.registry import get_engine
from app.models.schemas import (
    OutputFormat,
    Segment,
    TranscriptionResponse,
)
from app.utils.audio import convert_to_wav
from app.utils.format import format_output

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/audio", tags=["audio"], dependencies=[Depends(get_api_key)])

# 文件大小限制：25MB
MAX_FILE_SIZE = 25 * 1024 * 1024

# 直接支持的音频格式（无需转换）
NATIVE_AUDIO_FORMATS = {".wav"}


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


@router.post("/transcriptions")
async def create_transcription(
    file: Optional[UploadFile] = File(None),
    file_uuid: Optional[str] = Form(None, description="已上传文件的UUID（与 file 二选一）"),
    model: Optional[str] = Form(None, description="引擎名称"),
    language: Optional[str] = Form(None, description="语言代码"),
    response_format: OutputFormat = Form(OutputFormat.JSON, description="输出格式"),
    prompt: Optional[str] = Form(None, description="提示词"),
    stream: bool = Form(False, description="是否流式返回"),
    temperature: Optional[float] = Form(None, description="采样温度"),
):
    """创建语音识别任务（兼容 OpenAI 格式）。

    支持两种方式提供音频：
    1. 直接上传文件：使用 file 参数（最大 25MB）
    2. 使用已上传文件：使用 file_uuid 参数

    参数说明：
    - file: 音视频文件（与 file_uuid 二选一，最大 25MB）
    - file_uuid: 已上传文件的UUID（与 file 二选一）
    - model: 引擎名称（如 faster-whisper、wlk）
    - language: 语言代码（可选，如 zh、en、auto）
    - response_format: 输出格式（json、text、srt、vtt）
    - prompt: 提示词（可选）
    - stream: 是否流式返回（默认 false）
    - temperature: 采样温度（可选，0-1）

    流式返回格式（SSE）：
    - data: {"index": 0, "start": 0.0, "end": 2.5, "text": "Hello"}
    - data: {"done": true}
    """
    # 验证参数：file 和 file_uuid 至少提供一个
    if not file and not file_uuid:
        raise HTTPException(status_code=400, detail="必须提供 file 或 file_uuid 参数")

    try:
        # 获取音频数据和文件名
        data: bytes
        filename: str = "audio.wav"

        if file:
            # 验证文件大小
            data = await file.read()
            if len(data) > MAX_FILE_SIZE:
                size_mb = len(data) / (1024 * 1024)
                raise HTTPException(
                    status_code=400,
                    detail=f"文件大小超过限制: {size_mb:.1f}MB，最大支持 25MB。请使用文件上传接口先上传文件，然后通过 file_uuid 参数进行转录。"
                )
            filename = file.filename or "audio.wav"
        elif file_uuid:
            # 从已上传文件获取数据
            file_path = file_storage.get_file_path(file_uuid)
            if not file_path:
                raise HTTPException(status_code=404, detail=f"文件不存在: {file_uuid}")
            data = file_path.read_bytes()
            filename = file_path.name
        else:
            raise HTTPException(status_code=400, detail="必须提供 file 或 file_uuid 参数")

        # 检查是否需要转换为 WAV
        ext = Path(filename).suffix.lower()
        if ext not in NATIVE_AUDIO_FORMATS:
            logger.info("Converting %s to WAV for transcription", filename)
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_input:
                tmp_input.write(data)
                tmp_input_path = Path(tmp_input.name)

            tmp_wav_path: Path | None = None
            try:
                tmp_wav_path = convert_to_wav(tmp_input_path)
                data = tmp_wav_path.read_bytes()
                logger.info("Conversion complete: %s -> WAV (%d bytes)", filename, len(data))
            finally:
                tmp_input_path.unlink(missing_ok=True)
                if tmp_wav_path:
                    tmp_wav_path.unlink(missing_ok=True)

        # 获取引擎
        eng = get_engine(model)

        # 流式返回
        if stream:
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

        # 非流式返回
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
        elif response_format == OutputFormat.VERBOSE_JSON:
            # verbose_json 返回更详细的信息（OpenAI 兼容）
            return {
                "text": response.text,
                "segments": [
                    {
                        "id": seg.id,
                        "start": seg.start,
                        "end": seg.end,
                        "text": seg.text,
                    }
                    for seg in response.segments
                ],
                "language": response.language or "",
                "duration": response.duration or 0.0,
            }
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
