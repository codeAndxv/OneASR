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
    """验证 WebSocket 连接的 API Key（支持查询参数和 header）。"""
    # 查询参数
    key = ws.query_params.get("api_key", "")
    if key and verify_api_key(key):
        return True
    # Header（websockets 客户端不支持 query params，改用 header）
    auth = ws.headers.get("x-api-key", "")
    return verify_api_key(auth)
