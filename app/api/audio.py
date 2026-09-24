"""OpenAI-compatible transcription API — synchronous / streaming, ≤25 MB.

Endpoint: POST /v1/audio/transcriptions
Docs:     https://platform.openai.com/docs/api-reference/audio/createTranscription
"""

import json
import logging
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse, StreamingResponse

from app.api.auth import get_api_key
from app.core.config import app_config
from app.core.errors import OpenAIAPIException
from app.engines.registry import get_engine
from app.models.schemas import OutputFormat
from app.services.record_service import save_file_transcription_record
from app.utils.audio import convert_to_wav
from app.utils.format import format_output

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/audio", tags=["audio"], dependencies=[Depends(get_api_key)])

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB — same limit as OpenAI
NATIVE_AUDIO_FORMATS = {".wav"}


# ── 文件读取 ─────────────────────────────────────────────────────

async def _load_audio_data(file: UploadFile, request_id: str) -> tuple[bytes, str]:
    """Read uploaded audio file, enforcing the 25 MB limit."""
    data = await file.read()
    size_mb = len(data) / (1024 * 1024)
    logger.info("[transcriptions][%s] 收到文件: %s, %.2f MB", request_id, file.filename, size_mb)
    if len(data) > MAX_FILE_SIZE:
        raise OpenAIAPIException(
            status_code=400,
            message=f"File size exceeds limit: {size_mb:.1f}MB. The OpenAI-compatible endpoint supports up to 25MB. For large files, please use the OneASR service type in DuRT (via /v1/file/transcriptions, supporting up to 2GB).",
            error_type="invalid_request_error",
            param="file",
            code="file_too_large",
        )
    return data, file.filename or "audio.wav"


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


# ── 转录主接口（OpenAI 兼容）────────────────────────────────────

@router.post("/transcriptions")
async def create_transcription(
    request: Request,
    file: UploadFile = File(..., description="The audio file to transcribe"),
    model: str = Form(..., description="Model ID (provider name, e.g. whisper1)"),
    language: Optional[str] = Form(None, description="Language in ISO-639-1 (e.g. en, zh)"),
    languages: Optional[str] = Form(None, description="Possible languages (comma-separated ISO-639-1)"),
    response_format: OutputFormat = Form(OutputFormat.JSON, description="Output format"),
    prompt: Optional[str] = Form(None, description="Prompt to guide model style"),
    stream: bool = Form(False, description="Stream results via SSE"),
    temperature: Optional[float] = Form(None, description="Sampling temperature 0-1"),
    timestamp_granularities: Optional[str] = Form(None, description="word / segment / word,segment"),
    chunking_strategy: Optional[str] = Form(None, description="auto or VAD config"),
    include: Optional[str] = Form(None, description="Additional info (comma-separated, e.g. logprobs)"),
    keywords: Optional[str] = Form(None, description="Keywords to guide transcription"),
):
    """Transcribes audio into the input language.

    Compatible with POST /v1/audio/transcriptions (OpenAI).
    """
    rid = f"{int(time.time() * 1000)}"
    record_id = str(uuid.uuid4())
    t_start = time.time()

    logger.info(
        "[transcriptions][%s] model=%s lang=%s fmt=%s stream=%s file=%s content_type=%s",
        rid, model, language, response_format, stream,
        file.filename, request.headers.get("content-type"),
    )

    # Parse timestamp_granularities
    ts_granularities = None
    if timestamp_granularities:
        ts_granularities = [g.strip() for g in timestamp_granularities.split(",") if g.strip()]

    # Parse languages
    languages_list = None
    if languages:
        languages_list = [lang.strip() for lang in languages.split(",") if lang.strip()]

    # Parse include
    include_list = None
    if include:
        include_list = [item.strip() for item in include.split(",") if item.strip()]

    # Parse keywords
    keywords_list = None
    if keywords:
        keywords_list = [kw.strip() for kw in keywords.split(",") if kw.strip()]

    data: bytes = b""
    filename = "unknown"
    try:
        # 1. Read audio
        data, filename = await _load_audio_data(file, rid)

        # 2. Ensure WAV
        data = _ensure_wav(data, filename, rid)

        # 3. Get engine
        try:
            eng = get_engine(model)
        except (KeyError, ValueError) as e:
            logger.warning("[transcriptions][%s] 模型未找到: %s — %s", rid, model, e)
            raise OpenAIAPIException(
                status_code=404,
                message=f"The model '{model}' does not exist.",
                error_type="invalid_request_error",
                param="model",
                code="model_not_found",
            )
        logger.info("[transcriptions][%s] 引擎就绪: %s", rid, model)

        # 4. Stream / sync
        if stream:
            return await _handle_stream(rid, record_id, data, filename, eng, model, language,
                                        languages_list, response_format, t_start, ts_granularities)
        else:
            return await _handle_sync(rid, record_id, data, filename, eng, model, language,
                                        languages_list, response_format, t_start)

    except (HTTPException, OpenAIAPIException):
        raise
    except Exception as e:
        logger.exception("[transcriptions][%s] 语音识别失败: %s", rid, e)
        await save_file_transcription_record(
            record_id=record_id, filename=filename, file_size=len(data),
            engine_name=model, total_time=time.time() - t_start,
            is_completed=False, error_message=str(e),
        )
        raise OpenAIAPIException(
            status_code=500,
            message=f"Speech recognition failed: {e}",
            error_type="api_error",
            param=None,
            code="transcription_failed",
        )


# ── 流式 SSE（兼容 OpenAI 格式）────────────────────────────────

async def _handle_stream(rid, record_id, data, filename, eng, model, language,
                         languages, response_format, t_start, timestamp_granularities=None):
    """SSE stream compatible with OpenAI AudioTranscriptionStreamResult."""

    async def _generate():
        full_text = ""
        t_stream = time.time()
        try:
            async for seg in eng.transcribe_file_stream(data):
                delta_text = seg.text
                if delta_text:
                    full_text += delta_text
                    event = {
                        "type": "transcript.text.delta",
                        "delta": delta_text,
                        "start": getattr(seg, "start", 0.0),
                        "end": getattr(seg, "end", 0.0),
                        "is_endpoint": getattr(seg, "is_endpoint", True),
                    }
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            done_event = {"type": "transcript.text.done", "text": full_text}
            if languages:
                done_event["languages"] = [{"code": lang} for lang in languages]
            yield f"data: {json.dumps(done_event, ensure_ascii=False)}\n\n"

            logger.info("[transcriptions][%s] 流式完成: %d 字符, %.2fs",
                        rid, len(full_text), time.time() - t_stream)
            await save_file_transcription_record(
                record_id=record_id, filename=filename, file_size=len(data),
                engine_name=model,
                model_name=eng.model_name if hasattr(eng, "model_name") else None,
                device_info=eng.device if hasattr(eng, "device") else None,
                language=language, response_format="stream",
                result_length=len(full_text), total_time=time.time() - t_stream,
                is_completed=True,
            )
        except (ConnectionResetError, BrokenPipeError, OSError) as e:
            logger.info("[transcriptions][%s] SSE 客户端断开: %s", rid, e)
        except Exception as e:
            logger.exception("[transcriptions][%s] SSE 异常: %s", rid, e)
            error_event = {
                "type": "error",
                "error": {
                    "message": str(e),
                    "type": "api_error",
                    "param": None,
                    "code": "transcription_stream_failed",
                },
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
            await save_file_transcription_record(
                record_id=record_id, filename=filename, file_size=len(data),
                engine_name=model,
                model_name=eng.model_name if hasattr(eng, "model_name") else None,
                device_info=eng.device if hasattr(eng, "device") else None,
                language=language, response_format="stream",
                total_time=time.time() - t_stream,
                is_completed=False, error_message=str(e),
            )

    return StreamingResponse(_generate(), media_type="text/event-stream")


# ── 非流式（兼容 OpenAI 格式）──────────────────────────────────

async def _handle_sync(rid, record_id, data, filename, eng, model, language,
                       languages, response_format, t_start):
    """Non-streaming response compatible with OpenAI transcription formats."""
    t_recog = time.time()
    text, segments = await eng.transcribe_file(data)
    recog_time = time.time() - t_recog
    preview = (text[:60] + "...") if len(text) > 60 else text
    logger.info("[transcriptions][%s] 转录完成: %d 段, %d 字符, 耗时=%.2fs (识别=%.2fs), 文本='%s'",
                rid, len(segments), len(text), total_time, recog_time, preview)

    duration = segments[-1].end if segments else 0.0

    # Persist record
    await save_file_transcription_record(
        record_id=record_id, filename=filename, file_size=len(data),
        engine_name=model,
        model_name=eng.model_name if hasattr(eng, "model_name") else None,
        device_info=eng.device if hasattr(eng, "device") else None,
        language=language,
        response_format=response_format.value if hasattr(response_format, "value") else str(response_format),
        segment_count=len(segments), result_length=len(text),
        total_time=total_time, is_completed=True,
    )

    # Format output (OpenAI compatible)
    if response_format == OutputFormat.JSON:
        result = {"text": text}
        if languages:
            result["languages"] = [{"code": lang} for lang in languages]
        return result
    elif response_format == OutputFormat.VERBOSE_JSON:
        return {
            "text": text,
            "language": language or "",
            "duration": duration,
            "words": [
                {
                    "word": s.text,
                    "start": s.start,
                    "end": s.end,
                    "probability": 0.0,
                }
                for s in segments
            ],
            "segments": [
                {
                    "id": s.id,
                    "seek": 0,
                    "start": s.start,
                    "end": s.end,
                    "text": s.text,
                    "tokens": [],
                    "temperature": 0.0,
                    "avg_logprob": 0.0,
                    "compression_ratio": 0.0,
                    "no_speech_prob": 0.0,
                }
                for s in segments
            ],
        }
    elif response_format == OutputFormat.DIARIZED_JSON:
        return {
            "duration": duration,
            "language": language or "",
            "text": text,
            "segments": [
                {
                    "id": s.id,
                    "start": s.start,
                    "end": s.end,
                    "text": s.text,
                    "speaker": f"speaker_{s.speaker}" if s.speaker is not None else "unknown",
                }
                for s in segments
            ],
        }
    elif response_format == OutputFormat.TEXT:
        return PlainTextResponse(text, media_type="text/plain")
    else:
        return PlainTextResponse(
            format_output(text, segments, response_format),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename=transcript.{response_format.value}"},
        )
