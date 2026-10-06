"""Provider 信息 API。"""

import logging
import time

from fastapi import APIRouter, Depends

from server.core.config import API_VERSION, app_config, settings
from server.engines.registry import get_loaded_engines

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["providers"])


@router.get("/info")
async def get_service_info():
    """返回 OneASR 服务与接口协议版本信息。"""
    return {
        "service": "OneASR",
        "app_version": settings.app_version,
        "api_version": API_VERSION,
        "status": "ok",
    }


@router.get("/providers", dependencies=[Depends(get_api_key)])
async def list_providers():
    """返回已加载的 Provider 及其信息，包含模型配置。"""
    loaded = get_loaded_engines()
    providers = []

    for key, info in loaded.items():
        base_config = app_config.providers.get(info.provider_name)
        providers.append({
            "id": info.provider_name,
            "object": "provider",
            "created": int(time.time()),
            "owned_by": base_config.type if base_config else "unknown",
            "shutdown_date": "9999-12-31T23:59:59Z",
            "categories": base_config.categories if base_config else [],
            "functions": base_config.categories if base_config else [],
            "languages": base_config.languages if base_config else [],
            "features": base_config.features if base_config else ["asrAutoLanguageDetect"],
        })

    prov_names = [p["id"] for p in providers]
    logger.info(
        "[providers] 查询已加载 Provider: 共 %d 个 (%s)",
        len(providers),
        ", ".join(prov_names) if prov_names else "无",
    )

    return {
        "object": "list",
        "api_version": API_VERSION,
        "data": providers,
    }
