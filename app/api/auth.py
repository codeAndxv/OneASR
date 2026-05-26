from fastapi import Header, HTTPException, WebSocket

from app.core.config import app_config


def verify_api_key(key: str) -> bool:
    """验证 API Key 是否正确。"""
    return bool(app_config.api_key) and key == app_config.api_key


async def get_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    """FastAPI 依赖：从请求头 X-API-Key 获取并验证 API Key。"""
    if not verify_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="API Key 无效")
    return x_api_key


def verify_ws_api_key(ws: WebSocket) -> bool:
    """验证 WebSocket 连接的 API Key（通过查询参数传递）。"""
    key = ws.query_params.get("api_key", "")
    return verify_api_key(key)
