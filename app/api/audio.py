"""统一的语音识别 API 接口（参考 OpenAI 格式）。"""

import json
import logging
import tempfile
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse, StreamingResponse

from app.api.auth import get_api_key
from app.core.config import app_config
from app.db import async_session
from app.models.orm_models import UploadedFile
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
    logger.info("[models] 列出可用模型")
    models = []
    for name, config in app_config.engines.items():
        models.append({
            "id": name,
            "object": "model",
            "owned_by": "local",
            "type": config.type,
            "model_name": config.model_name,
        })
    logger.info("[models] 共 %d 个模型: %s", len(models), [m["id"] for m in models])
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
    """创建语音识别任务（兼容 OpenAI 格式）。"""
    request_id = f"{int(time.time() * 1000)}"
    logger.info(
        "[transcriptions][%s] 收到请求 — model=%s, language=%s, format=%s, stream=%s, "
        "file=%s, file_uuid=%s, prompt=%s, temperature=%s",
        request_id,
        model,
        language,
        response_format,
        stream,
        file.filename if file else None,
        file_uuid,
        (prompt[:50] + "...") if prompt and len(prompt) > 50 else prompt,
        temperature,
    )

    # 验证参数：file 和 file_uuid 至少提供一个
    if not file and not file_uuid:
        logger.warning("[transcriptions][%s] 缺少 file 和 file_uuid 参数", request_id)
        raise HTTPException(status_code=400, detail="必须提供 file 或 file_uuid 参数")

    t_start = time.time()

    try:
        # 获取音频数据和文件名
        data: bytes
        filename: str = "audio.wav"

        if file:
            # 验证文件大小
            data = await file.read()
            file_size_mb = len(data) / (1024 * 1024)
            logger.info(
                "[transcriptions][%s] 收到文件: %s, 大小: %.2f MB (%d bytes), content_type: %s",
                request_id, file.filename, file_size_mb, len(data), file.content_type,
            )
            if len(data) > MAX_FILE_SIZE:
                logger.warning("[transcriptions][%s] 文件超过 25MB 限制: %.2f MB", request_id, file_size_mb)
                raise HTTPException(
                    status_code=400,
                    detail=f"文件大小超过限制: {file_size_mb:.1f}MB，最大支持 25MB。请使用文件上传接口先上传文件，然后通过 file_uuid 参数进行转录。"
                )
            filename = file.filename or "audio.wav"
        elif file_uuid:
            # 从数据库查找已上传文件
            from pathlib import Path as _Path
            from sqlalchemy import select
            async with async_session() as _session:
                result = await _session.execute(
                    select(UploadedFile).where(UploadedFile.file_id == file_uuid)
                )
                record = result.scalar_one_or_none()
            if not record:
                logger.warning("[transcriptions][%s] file_uuid=%s 不存在", request_id, file_uuid)
                raise HTTPException(status_code=404, detail=f"文件不存在: {file_uuid}")
            file_path = _Path(record.storage_path)
            if not file_path.exists():
                logger.warning("[transcriptions][%s] file_uuid=%s 磁盘文件丢失", request_id, file_uuid)
                raise HTTPException(status_code=404, detail=f"文件已丢失: {file_uuid}")
            data = file_path.read_bytes()
            filename = record.filename
            logger.info(
                "[transcriptions][%s] 从 UUID 加载文件: %s, 大小: %.2f MB",
                request_id, file_uuid, len(data) / (1024 * 1024),
            )
        else:
            raise HTTPException(status_code=400, detail="必须提供 file 或 file_uuid 参数")

        # 检查是否需要转换为 WAV
        ext = Path(filename).suffix.lower()
        if ext not in NATIVE_AUDIO_FORMATS:
            logger.info("[transcriptions][%s] 格式 %s 需要转换为 WAV", request_id, ext)
            t_convert_start = time.time()
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_input:
                tmp_input.write(data)
                tmp_input_path = Path(tmp_input.name)

            tmp_wav_path: Path | None = None
            try:
                tmp_wav_path = convert_to_wav(tmp_input_path)
                data = tmp_wav_path.read_bytes()
                convert_time = time.time() - t_convert_start
                logger.info(
                    "[transcriptions][%s] 转换完成: %s -> WAV (%d bytes), 耗时: %.2fs",
                    request_id, filename, len(data), convert_time,
                )
            finally:
                tmp_input_path.unlink(missing_ok=True)
                if tmp_wav_path:
                    tmp_wav_path.unlink(missing_ok=True)

        # 获取引擎
        logger.info("[transcriptions][%s] 正在获取引擎: %s", request_id, model)
        t_engine_start = time.time()
        eng = get_engine(model)
        engine_time = time.time() - t_engine_start
        logger.info("[transcriptions][%s] 引擎就绪: %s (%.2fs)", request_id, model, engine_time)

        # 流式返回
        if stream:
            logger.info("[transcriptions][%s] 开始流式转录", request_id)

            async def stream_generator():
                idx = 0
                t_stream_start = time.time()
                try:
                    async for seg in eng.transcribe_file_stream(data):
                        event = {"index": idx, "start": seg.start, "end": seg.end, "text": seg.text}
                        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                        if idx % 10 == 0:
                            logger.debug(
                                "[transcriptions][%s] 流式段落 #%d: [%.2f-%.2f] %s",
                                request_id, idx, seg.start, seg.end, seg.text[:80],
                            )
                        idx += 1
                    yield 'data: {"done": true}\n\n'
                    total_time = time.time() - t_stream_start
                    logger.info(
                        "[transcriptions][%s] 流式转录完成: %d 段, 总耗时: %.2fs",
                        request_id, idx, total_time,
                    )
                except (ConnectionResetError, BrokenPipeError, OSError) as e:
                    logger.info("[transcriptions][%s] SSE 流客户端已断开: %s", request_id, e)
                except Exception as e:
                    logger.exception("[transcriptions][%s] SSE 流异常: %s", request_id, e)
                    yield f'data: {json.dumps({"error": str(e)}, ensure_ascii=False)}\n\n'

            return StreamingResponse(
                stream_generator(),
                media_type="text/event-stream",
            )

        # 非流式返回
        logger.info("[transcriptions][%s] 开始非流式转录", request_id)
        t_recog_start = time.time()
        text, segments = await eng.transcribe_file(data)
        recog_time = time.time() - t_recog_start
        logger.info(
            "[transcriptions][%s] 转录完成: %d 段, 文本长度 %d 字符, 耗时: %.2fs",
            request_id, len(segments), len(text), recog_time,
        )

        # 构建响应
        response = TranscriptionResponse(
            text=text,
            segments=[
                Segment(id=i, start=seg.start, end=seg.end, text=seg.text)
                for i, seg in enumerate(segments)
            ],
            engine=model or app_config.default_engine,
        )

        total_time = time.time() - t_start
        logger.info("[transcriptions][%s] 响应完成, format=%s, 总耗时: %.2fs", request_id, response_format, total_time)

        # 根据格式返回
        if response_format == OutputFormat.JSON:
            return response
        elif response_format == OutputFormat.VERBOSE_JSON:
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
        logger.exception("[transcriptions][%s] 语音识别失败: %s", request_id, e)
        raise HTTPException(status_code=500, detail=f"识别失败: {e}")


@router.get("/transcriptions/{transcription_id}")
async def get_transcription(transcription_id: str):
    """获取语音识别任务状态（兼容 OpenAI 格式，暂未实现）。"""
    raise HTTPException(status_code=501, detail="异步任务功能暂未实现")


@router.delete("/transcriptions/{transcription_id}")
async def delete_transcription(transcription_id: str):
    """删除语音识别任务（兼容 OpenAI 格式，暂未实现）。"""
    raise HTTPException(status_code=501, detail="异步任务功能暂未实现")
