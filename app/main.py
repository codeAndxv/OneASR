import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import audio, media, model, provider, realtime, tasks, upload
from app.core.config import settings

# 配置日志级别
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

logger = logging.getLogger(__name__)


async def _load_all_providers():
    """后台并发加载所有 Provider（本地引擎可能需要下载模型）。"""
    from app.core.config import app_config
    from app.engines.registry import get_engine

    async def _load_one(name: str):
        try:
            logger.info("[startup] 正在加载 Provider: %s", name)
            await asyncio.to_thread(get_engine, name)
            logger.info("[startup] Provider 加载成功: %s", name)
        except Exception as e:
            logger.warning("[startup] Provider 加载失败: %s — %s", name, e)

    # 并发加载所有 Provider，总耗时 = 最慢的那个
    await asyncio.gather(*[_load_one(name) for name in app_config.providers])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库、后台加载所有 Provider。"""
    from app.db import init_db
    await init_db()

    # 清洗重启前未完成的媒体下载任务，避免状态永久卡在 pending/running
    from app.services import media_service
    n = await media_service.reset_stale_tasks()
    if n:
        logger.info("[startup] 重置 %d 个未完成的媒体下载任务为 failed", n)

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

# 模型列表 API（兼容 OpenAI /v1/models）
app.include_router(model.router)

# Provider 信息 API
app.include_router(provider.router)

# 文件上传和管理 API
app.include_router(upload.router)

# 流式识别 API（OpenAI Realtime Transcription 协议）
app.include_router(realtime.router)

# 媒体 URL 异步下载（抖音/TikTok/B站/YouTube）
app.include_router(media.router)

# 异步转录任务 API（大文件 ≤2GB，长时间转录）
app.include_router(tasks.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
