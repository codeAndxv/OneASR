import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import audio, file_transcription, file_upload, model, provider, realtime, realtime_ext
from app.core.config import settings

# 配置日志级别
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库、同步校验并加载所有已启用的 Provider。"""
    from app.db import init_db
    await init_db()

    # 清洗重启前未完成的媒体下载任务，避免状态永久卡在 pending/running
    from app.services import media_service
    n = await media_service.reset_stale_tasks()
    if n:
        logger.info("[startup] 重置 %d 个未完成的媒体下载任务为 failed", n)

    # 启动时同步校验并加载所有已启用的 Provider
    # 若配置了路径但模型缺失或加载失败，直接抛出异常终止服务启动 (Fail-Fast)
    from app.core.config import app_config
    from app.engines.registry import get_engine

    enabled_providers = [
        name for name, cfg in app_config.providers.items()
        if getattr(cfg, "enable", True)
    ]
    logger.info("[startup] 待加载启用的 Provider: %s", enabled_providers)
    for name in enabled_providers:
        try:
            logger.info("[startup] 正在加载 Provider: %s", name)
            await asyncio.to_thread(get_engine, name)
            logger.info("[startup] Provider 加载成功: %s", name)
        except Exception as e:
            logger.error("[startup] Provider [%s] 加载失败，终止服务启动: %s", name, e)
            raise RuntimeError(f"Provider [{name}] 加载失败: {e}") from e

    yield


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 统一 API（参考 OpenAI 格式）
app.include_router(audio.router)

# 模型列表 API（兼容 OpenAI /v1/models）
app.include_router(model.router)

# Provider 信息 API
app.include_router(provider.router)

# 文件管理 API（上传/列表/查询/删除）
app.include_router(file_upload.router)

# 流式识别 API（OpenAI Realtime Transcription 协议）
app.include_router(realtime.router)

# 流式识别 API（扩展版，/v1/realtimeext）
app.include_router(realtime_ext.router)

# 文件转录 API（异步任务，大文件 ≤2GB，长时间转录）
app.include_router(file_transcription.router)


# ── 全局错误处理（兼容 FastAPI detail 与 OpenAI error.message）──────

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import (
    OpenAIAPIException,
    build_openai_error_json_response,
    get_default_error_code,
    get_default_error_type,
)


@app.exception_handler(OpenAIAPIException)
async def openai_api_exception_handler(request: Request, exc: OpenAIAPIException):
    """处理自定义 OpenAI API 异常。"""
    return build_openai_error_json_response(
        status_code=exc.status_code,
        message=exc.message,
        error_type=exc.error_type,
        param=exc.param,
        code=exc.code,
        raw_detail=exc.detail,
        headers=exc.headers,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """统一 HTTP 异常格式，兼容 detail 字典/字符串与 OpenAI error 规范。"""
    if isinstance(exc.detail, dict):
        message = exc.detail.get("message", str(exc.detail))
        error_type = exc.detail.get("type", get_default_error_type(exc.status_code))
        param = exc.detail.get("param")
        code = exc.detail.get("code", get_default_error_code(exc.status_code))
        raw_detail = exc.detail
    else:
        message = str(exc.detail)
        error_type = get_default_error_type(exc.status_code)
        param = None
        code = get_default_error_code(exc.status_code)
        raw_detail = exc.detail

    return build_openai_error_json_response(
        status_code=exc.status_code,
        message=message,
        error_type=error_type,
        param=param,
        code=code,
        raw_detail=raw_detail,
        headers=exc.headers,
    )


@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """处理 Starlette 底层抛出的 HTTP 异常（如 404 Not Found 等）。"""
    message = str(exc.detail)
    return build_openai_error_json_response(
        status_code=exc.status_code,
        message=message,
        error_type=get_default_error_type(exc.status_code),
        param=None,
        code=get_default_error_code(exc.status_code),
        raw_detail=exc.detail,
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """统一参数校验异常格式，提取首个失败参数为 param。"""
    errors = exc.errors()
    message = "; ".join(f"{'.'.join(str(loc) for loc in e.get('loc', []))}: {e.get('msg', '')}" for e in errors)
    first_param = None
    if errors:
        loc = errors[0].get("loc", [])
        if len(loc) > 1:
            first_param = str(loc[-1])
        elif len(loc) == 1:
            first_param = str(loc[0])

    return build_openai_error_json_response(
        status_code=400,
        message=message,
        error_type="invalid_request_error",
        param=first_param,
        code="validation_error",
        raw_detail=errors,
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """全局兜底异常处理器，避免 500 时返回非 JSON 文本。"""
    logger.exception("[unhandled_exception] %s: %s", request.url.path, exc)
    return build_openai_error_json_response(
        status_code=500,
        message=f"Internal Server Error: {str(exc)}",
        error_type="api_error",
        param=None,
        code="internal_error",
        raw_detail=str(exc),
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
