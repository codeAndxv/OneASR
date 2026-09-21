"""Model listing API — compatible with OpenAI GET /v1/models."""

import logging
import time

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
            "created": int(time.time()),
            "owned_by": engine_config.type,
            "shutdown_date": None,
        })

    logger.info("[models] 查询可用模型: 共 %d 个", len(providers))

    return {
        "object": "list",
        "data": providers,
    }


@router.get("/models/{model_id}")
async def retrieve_model(model_id: str):
    """返回单个模型信息（兼容 OpenAI GET /v1/models/{model}）。"""
    from app.core.errors import OpenAIAPIException

    if model_id not in app_config.providers:
        raise OpenAIAPIException(
            status_code=404,
            message=f"The model '{model_id}' does not exist.",
            error_type="invalid_request_error",
            param="model",
            code="model_not_found",
        )
    cfg = app_config.providers[model_id]
    return {
        "id": model_id,
        "object": "model",
        "created": int(time.time()),
        "owned_by": cfg.type,
        "shutdown_date": None,
    }

