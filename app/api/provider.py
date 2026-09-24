"""Provider 信息 API。"""

import logging
import time

from fastapi import APIRouter, Depends

from app.api.auth import get_api_key
from app.core.config import app_config
from app.engines.registry import get_loaded_engines

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["providers"], dependencies=[Depends(get_api_key)])


@router.get("/providers")
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
            "functions": base_config.functions if base_config else [],
            "languages": base_config.languages if base_config else [],
        })

    prov_names = [p["id"] for p in providers]
    logger.info(
        "[providers] 查询已加载 Provider: 共 %d 个 (%s)",
        len(providers),
        ", ".join(prov_names) if prov_names else "无",
    )

    return {
        "object": "list",
        "data": providers,
    }
