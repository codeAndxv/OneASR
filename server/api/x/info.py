"""OneASR system & protocol version information API (/v1/x/info)."""

import json
from fastapi import APIRouter, Depends

from server.api.auth import get_api_key
from server.api.x.system import get_local_lan_ip
from server.core.config import API_VERSION, settings
from server.core.paths import get_settings_path

router = APIRouter(prefix="/v1/x", tags=["x-info"], dependencies=[Depends(get_api_key)])


@router.get("/info")
async def get_service_info():
    """返回 OneASR 服务与接口协议版本信息及当前网络绑定状态。"""
    settings_file = get_settings_path()
    host = "127.0.0.1"
    port = 8020
    if settings_file.is_file():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
                if "host" in data:
                    host = str(data["host"])
                if "port" in data:
                    port = int(data["port"])
        except Exception:
            pass

    return {
        "service": "OneASR",
        "app_version": settings.app_version,
        "api_version": API_VERSION,
        "status": "ok",
        "host": host,
        "port": port,
        "lan_ip": get_local_lan_ip(),
    }
