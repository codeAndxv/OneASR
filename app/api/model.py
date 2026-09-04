"""Model listing API — compatible with OpenAI GET /v1/models."""

import logging

from fastapi import APIRouter, Depends

from app.api.auth import get_api_key
from app.core.config import app_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["models"], dependencies=[Depends(get_api_key)])


@router.get("/models")
async def list_models():
    """返回可用的模型列表（兼容 OpenAI /v1/models）。"""
    providers = []
    for name, engine_config in app_config.providers.items():
        providers.append({
            "id": name,
            "object": "model",
            "created": 0,
            "owned_by": engine_config.type,
        })

    logger.info("[models] 查询可用模型: 共 %d 个", len(providers))

    return {
        "object": "list",
        "data": providers,
    }
