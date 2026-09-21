from typing import Optional
from fastapi import Header, HTTPException, WebSocket

from app.core.config import app_config
from app.core.errors import OpenAIAPIException


def verify_api_key(key: str) -> bool:
    """验证 API Key 是否正确。"""
    return bool(app_config.api_key) and key == app_config.api_key


async def get_api_key(authorization: Optional[str] = Header(None)) -> str:
    """FastAPI 依赖：从 Authorization header 获取并验证 API Key。
    格式：Authorization: Bearer <key>
    """
    if not authorization:
        raise OpenAIAPIException(
            status_code=401,
            message="You didn't provide an API key. You need to provide your API key in an Authorization header using Bearer auth (i.e. Authorization: Bearer YOUR_KEY).",
            error_type="authentication_error",
            param=None,
            code="invalid_api_key",
        )
    if not authorization.startswith("Bearer "):
        raise OpenAIAPIException(
            status_code=401,
            message="You must provide a valid API key in the Authorization header using 'Bearer <token>' format.",
            error_type="authentication_error",
            param=None,
            code="invalid_api_key",
        )
    key = authorization[7:].strip()
    if not verify_api_key(key):
        raise OpenAIAPIException(
            status_code=401,
            message="Incorrect API key provided.",
            error_type="authentication_error",
            param=None,
            code="invalid_api_key",
        )
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
