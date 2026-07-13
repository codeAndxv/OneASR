"""统一的语音识别 API 接口（参考 OpenAI 格式）。"""

import json
import logging
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse, StreamingResponse

from app.api.auth import get_api_key
from app.core.config import app_config
from app.engines.registry import get_engine
from app.models.schemas import OutputFormat, Segment, TranscriptionResponse
from app.services.file_service import get_uploaded_file
from app.services.record_service import save_file_transcription_record
from app.utils.audio import convert_to_wav
from app.utils.format import format_output

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/audio", tags=["audio"], dependencies=[Depends(get_api_key)])

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB
NATIVE_AUDIO_FORMATS = {".wav"}


# ── 引擎元数据 ───────────────────────────────────────────────────

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
    return {"object": "list", "data": models}


# ── 文件读取（内联上传 或 UUID）─────────────────────────────────

async def _load_audio_data(
    file: UploadFile | None,
    file_uuid: str | None,
    request_id: str,
) -> tuple[bytes, str]:
    """返回 (音频字节, 文件名)。"""
    if file:
        data = await file.read()
        size_mb = len(data) / (1024 * 1024)
        logger.info("[transcriptions][%s] 收到文件: %s, %.2f MB", request_id, file.filename, size_mb)
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"文件大小超过限制: {size_mb:.1f}MB，最大支持 25MB。"
                       "请使用文件上传接口先上传文件，然后通过 file_uuid 参数进行转录。",
            )
        return data, file.filename or "audio.wav"

    if file_uuid:
        info = await get_uploaded_file(file_uuid)
        if info is None:
            raise HTTPException(status_code=404, detail=f"文件不存在: {file_uuid}")
        try:
            data = info.read_bytes()
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"文件已丢失: {file_uuid}")
        logger.info("[transcriptions][%s] 从 UUID 加载: %s, %.2f MB",
                     request_id, info.filename, len(data) / (1024 * 1024))
        return data, info.filename

    raise HTTPException(status_code=400, detail="必须提供 file 或 file_uuid 参数")


# ── 音频格式转换 ─────────────────────────────────────────────────

def _ensure_wav(data: bytes, filename: str, request_id: str) -> bytes:
    """非 WAV 格式转为 WAV；已是 WAV 则原样返回。"""
    ext = Path(filename).suffix.lower()
    if ext in NATIVE_AUDIO_FORMATS:
        return data
    logger.info("[transcriptions][%s] 格式 %s 需要转换为 WAV", request_id, ext)
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_in:
        tmp_in.write(data)
        tmp_in_path = Path(tmp_in.name)
    tmp_wav: Path | None = None
    try:
        tmp_wav = convert_to_wav(tmp_in_path)
        return tmp_wav.read_bytes()
    finally:
        tmp_in_path.unlink(missing_ok=True)
        if tmp_wav:
            tmp_wav.unlink(missing_ok=True)


# ── 转录主接口 ───────────────────────────────────────────────────

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
    rid = f"{int(time.time() * 1000)}"
    record_id = str(uuid.uuid4())
    t_start = time.time()

    logger.info("[transcriptions][%s] model=%s lang=%s fmt=%s stream=%s file=%s uuid=%s",
                rid, model, language, response_format, stream,
                file.filename if file else None, file_uuid)

    try:
        # 1. 读取音频
        data, filename = await _load_audio_data(file, file_uuid, rid)

        # 2. 格式转换
        data = _ensure_wav(data, filename, rid)

        # 3. 获取引擎
        eng = get_engine(model)
        logger.info("[transcriptions][%s] 引擎就绪: %s", rid, model)

        # 4. 流式 / 非流式
        if stream:
            return await _handle_stream(rid, record_id, data, filename, eng, model, language,
                                        response_format, t_start)
        else:
            return await _handle_sync(rid, record_id, data, filename, eng, model, language,
                                      response_format, t_start)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[transcriptions][%s] 语音识别失败: %s", rid, e)
        await save_file_transcription_record(
            record_id=record_id,
            filename=locals().get("filename", "unknown"),
            file_size=len(data) if "data" in locals() else 0,
            engine_name=model or app_config.default_engine,
            total_time=time.time() - t_start,
            is_completed=False,
            error_message=str(e),
        )
        raise HTTPException(status_code=500, detail=f"识别失败: {e}")


# ── 流式 SSE ────────────────────────────────────────────────────

async def _handle_stream(rid, record_id, data, filename, eng, model, language,
                         response_format, t_start):
    async def _generate():
        idx = 0
        t_stream = time.time()
        try:
            async for seg in eng.transcribe_file_stream(data):
                event = {"index": idx, "start": seg.start, "end": seg.end, "text": seg.text}
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                idx += 1
            yield 'data: {"done": true}\n\n'
            logger.info("[transcriptions][%s] 流式完成: %d 段, %.2fs",
                        rid, idx, time.time() - t_stream)
            await save_file_transcription_record(
                record_id=record_id, filename=filename, file_size=len(data),
                engine_name=model or app_config.default_engine,
                model_name=eng.model_name if hasattr(eng, "model_name") else None,
                device_info=eng.device if hasattr(eng, "device") else None,
                language=language, response_format="stream",
                segment_count=idx, total_time=time.time() - t_stream,
                is_completed=True,
            )
        except (ConnectionResetError, BrokenPipeError, OSError) as e:
            logger.info("[transcriptions][%s] SSE 客户端断开: %s", rid, e)
        except Exception as e:
            logger.exception("[transcriptions][%s] SSE 异常: %s", rid, e)
            yield f'data: {json.dumps({"error": str(e)}, ensure_ascii=False)}\n\n'
            await save_file_transcription_record(
                record_id=record_id, filename=filename, file_size=len(data),
                engine_name=model or app_config.default_engine,
                model_name=eng.model_name if hasattr(eng, "model_name") else None,
                device_info=eng.device if hasattr(eng, "device") else None,
                language=language, response_format="stream",
                total_time=time.time() - t_stream,
                is_completed=False, error_message=str(e),
            )

    return StreamingResponse(_generate(), media_type="text/event-stream")


# ── 非流式 ──────────────────────────────────────────────────────

async def _handle_sync(rid, record_id, data, filename, eng, model, language,
                       response_format, t_start):
    t_recog = time.time()
    text, segments = await eng.transcribe_file(data)
    recog_time = time.time() - t_recog
    total_time = time.time() - t_start
    logger.info("[transcriptions][%s] 转录完成: %d 段, %d 字符, %.2fs",
                rid, len(segments), len(text), recog_time)

    response = TranscriptionResponse(
        text=text,
        segments=[Segment(id=i, start=s.start, end=s.end, text=s.text) for i, s in enumerate(segments)],
        engine=model or app_config.default_engine,
    )

    # 持久化
    await save_file_transcription_record(
        record_id=record_id, filename=filename, file_size=len(data),
        engine_name=model or app_config.default_engine,
        model_name=eng.model_name if hasattr(eng, "model_name") else None,
        device_info=eng.device if hasattr(eng, "device") else None,
        language=language,
        response_format=response_format.value if hasattr(response_format, "value") else str(response_format),
        segment_count=len(segments), result_length=len(text),
        total_time=total_time, is_completed=True,
    )

    # 格式化输出
    if response_format == OutputFormat.JSON:
        return response
    elif response_format == OutputFormat.VERBOSE_JSON:
        return {
            "text": response.text,
            "segments": [{"id": s.id, "start": s.start, "end": s.end, "text": s.text} for s in response.segments],
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


# ── 占位接口 ────────────────────────────────────────────────────

@router.get("/transcriptions/{transcription_id}")
async def get_transcription(transcription_id: str):
    raise HTTPException(status_code=501, detail="异步任务功能暂未实现")


@router.delete("/transcriptions/{transcription_id}")
async def delete_transcription(transcription_id: str):
    raise HTTPException(status_code=501, detail="异步任务功能暂未实现")
