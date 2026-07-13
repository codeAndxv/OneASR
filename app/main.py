import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import audio, provider, record, stream, upload
from app.core.config import settings

logger = logging.getLogger(__name__)


async def _load_all_providers():
    """后台加载所有 Provider（本地引擎可能需要下载模型）。"""
    from app.core.config import app_config
    from app.engines.registry import get_engine

    for name, config in app_config.providers.items():
        try:
            logger.info("[startup] 正在加载 Provider: %s (engine=%s, type=%s)",
                        name, config.engine_name, config.type)
            get_engine(name)
            logger.info("[startup] Provider 加载成功: %s", name)
        except Exception as e:
            logger.warning("[startup] Provider 加载失败: %s — %s", name, e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库、后台加载所有 Provider。"""
    from app.db import init_db
    await init_db()

    # 后台加载所有 Provider，不阻塞服务启动
    load_task = asyncio.create_task(_load_all_providers())

    yield

    # 关闭时等待加载任务完成（如果还在进行）
    if not load_task.done():
        logger.info("[shutdown] 等待 Provider 加载完成...")
        await load_task


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

# Provider 信息 API
app.include_router(provider.router)

# 文件上传和管理 API
app.include_router(upload.router)

# 转录记录查询 API
app.include_router(record.router)

# 流式识别 API
app.include_router(stream.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
