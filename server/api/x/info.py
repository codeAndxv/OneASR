"""OneASR system & protocol version information API (/v1/x/info)."""

from fastapi import APIRouter, Depends

from server.api.auth import get_api_key
from server.core.config import API_VERSION, settings

router = APIRouter(prefix="/v1/x", tags=["x-info"], dependencies=[Depends(get_api_key)])


@router.get("/info")
async def get_service_info():
    """返回 OneASR 服务与接口协议版本信息。"""
    return {
        "service": "OneASR",
        "app_version": settings.app_version,
        "api_version": API_VERSION,
        "status": "ok",
    }
