import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import audio, models, records, stream, upload
from app.core.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库、预加载引擎模型。"""
    from app.db import init_db
    await init_db()

    try:
        from app.engines.registry import get_engine
        get_engine("whisperlivekit")
        logger.info("WLK 引擎预加载完成")
    except Exception as e:
        logger.warning("WLK 引擎预加载失败（首次请求时会重新加载）: %s", e)
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

# 引擎和模型信息 API
app.include_router(models.router)

# 文件上传和管理 API
app.include_router(upload.router)

# 转录记录查询 API
app.include_router(records.router)

# 流式识别 API
app.include_router(stream.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
