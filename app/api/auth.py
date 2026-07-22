from fastapi import Header, HTTPException, WebSocket

from app.core.config import app_config


def verify_api_key(key: str) -> bool:
    """验证 API Key 是否正确。"""
    return bool(app_config.api_key) and key == app_config.api_key


async def get_api_key(authorization: str = Header(...)) -> str:
    """FastAPI 依赖：从 Authorization header 获取并验证 API Key。
    格式：Authorization: Bearer <key>
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="需要 Authorization: Bearer <key> 格式")
    key = authorization[7:].strip()
    if not verify_api_key(key):
        raise HTTPException(status_code=401, detail="API Key 无效")
    return key


def verify_ws_api_key(ws: WebSocket) -> bool:
    """验证 WebSocket 连接的 API Key（支持查询参数和 Authorization header）。"""
    # 查询参数
    key = ws.query_params.get("api_key", "")
    if key and verify_api_key(key):
        return True
    # Header: Authorization: Bearer
    auth_header = ws.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        bearer_key = auth_header[7:].strip()
        if verify_api_key(bearer_key):
            return True
    return False
