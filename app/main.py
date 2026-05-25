import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import file, stream
from app.core.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时预加载引擎模型。"""
    # 预加载 wlk 引擎（WhisperLiveKit 模型较大，首次加载需要时间）
    try:
        from app.engines.registry import get_engine
        get_engine("wlk")
        logger.info("WLK 引擎预加载完成")
    except Exception as e:
        logger.warning("WLK 引擎预加载失败（首次请求时会重新加载）: %s", e)
    yield


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.include_router(file.router)
app.include_router(stream.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
