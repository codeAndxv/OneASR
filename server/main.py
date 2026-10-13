import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.api.standard import (
    audio as std_audio,
    models as std_models,
    realtime as std_realtime,
)
from server.api.x import (
    audio as x_audio,
    files as x_files,
    info as x_info,
    media as x_media,
    models as x_models,
    realtime as x_realtime,
)
from server.core.config import settings

# 配置日志级别
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

logger = logging.getLogger(__name__)


async def _idle_model_reaper(interval_seconds: int):
    """后台轻量巡检任务：定期扫描并卸载超过 keep_alive 空闲时间且无活跃任务的模型。"""
    from server.engines.registry import unload_idle_engines
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            await asyncio.to_thread(unload_idle_engines)
        except Exception as e:
            logger.warning("[ModelManager] 空闲模型巡检异常: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：
    1. 初始化数据库与清洗过期任务；
    2. 对所有 enable=true 的 Provider 执行轻量级路径与配置校验 (Fail-Fast，零内存开销)；
    3. 仅对 preload=true 的 Provider (如实时流式小模型 xasr) 预加载权重；
    4. 启动后台 keep_alive 空闲模型自动释放巡检协程，并在退出时释放所有模型。
    """
    from server.db import init_db
    await init_db()

    from server.services import media_service
    n = await media_service.reset_stale_tasks()
    if n:
        logger.info("[startup] 重置 %d 个未完成的媒体下载任务为 failed", n)

    from server.core.config import app_config
    from server.engines.registry import get_engine, unload_all, validate_provider

    enabled_providers = [
        name for name, cfg in app_config.providers.items()
        if getattr(cfg, "enable", True)
    ]
    logger.info("[startup] 启用的 Provider 列表: %s", enabled_providers)

    for name in enabled_providers:
        cfg = app_config.providers[name]
        try:
            if cfg.preload:
                logger.info("[startup] 正在预热加载 Provider (preload=true): %s", name)
                await asyncio.to_thread(get_engine, name)
                logger.info("[startup] Provider 预热完成: %s (keep_alive=%ss)", name, cfg.keep_alive)
            else:
                logger.info("[startup] 正在校验按需加载 Provider (preload=false): %s", name)
                await asyncio.to_thread(validate_provider, name)
                logger.info("[startup] Provider 路径校验通过 (待命按需加载): %s (keep_alive=%ss)", name, cfg.keep_alive)
        except Exception as e:
            logger.error("[startup] Provider [%s] 校验或加载失败，终止服务启动: %s", name, e)
            raise RuntimeError(f"Provider [{name}] 加载失败: {e}") from e

    reaper_task = asyncio.create_task(
        _idle_model_reaper(app_config.model_manager.cleanup_interval)
    )
    try:
        yield
    finally:
        reaper_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reaper_task
        unloaded = await asyncio.to_thread(unload_all, True)
        if unloaded:
            logger.info("[shutdown] 已释放所有已加载模型: %s", unloaded)


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── OpenAI 标准兼容层 (/v1) ─────────────────────────────────────────
app.include_router(std_audio.router)         # POST /v1/audio/transcriptions
app.include_router(std_models.router)        # GET  /v1/models, GET /v1/models/{model_id}
app.include_router(std_realtime.router)      # WS   /v1/realtime

# ── OneASR 增强原生层 (/v1/x) ─────────────────────────────────────────
app.include_router(x_audio.router)           # POST /v1/x/audio/transcriptions (async tasks & SSE)
app.include_router(x_files.router)           # POST /v1/x/files (upload, dedup & CRUD)
app.include_router(x_models.router)          # GET  /v1/x/models (capability matrix & load/unload)
app.include_router(x_realtime.router)        # WS   /v1/x/realtime (sentence events & timestamps)
app.include_router(x_media.router)           # POST /v1/x/media (yt-dlp parsing & download)
app.include_router(x_info.router)            # GET  /v1/x/info (service version & status)


# ── 全局错误处理（兼容 FastAPI detail 与 OpenAI error.message）──────

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from server.core.errors import (
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


# ── 前端 Web UI 静态文件挂载（若存在构建产物）──────────────────
from pathlib import Path
from fastapi.staticfiles import StaticFiles

_dist_dir = Path(__file__).parent.parent / "web" / "dist"
if _dist_dir.exists():
    app.mount("/", StaticFiles(directory=str(_dist_dir), html=True), name="static_web")
