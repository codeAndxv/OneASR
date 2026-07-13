"""Provider 信息 API。"""

import logging

from fastapi import APIRouter, Depends

from app.api.auth import get_api_key
from app.core.config import app_config
from app.engines.registry import get_loaded_engines

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["providers"], dependencies=[Depends(get_api_key)])


@router.get("/providers")
async def list_providers():
    """返回已加载的 Provider 及其信息。"""
    loaded = get_loaded_engines()
    providers = []

    for key, info in loaded.items():
        base_config = app_config.providers.get(info.provider_name)
        providers.append({
            "id": info.provider_name,
            "engine": info.engine_name,
            "model": info.model_name,
            "device": info.device,
            "compute_type": info.compute_type,
            "type": base_config.type if base_config else "unknown",
            "streaming": info.streaming,
            "loaded": True,
        })

    logger.info(
        "[providers] 查询已加载 Provider: 共 %d 个",
        len(providers),
    )

    return {
        "object": "list",
        "data": providers,
        "default": app_config.default_provider,
    }
