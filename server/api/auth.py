from typing import Optional
from fastapi import Header, HTTPException, WebSocket

from server.core.config import app_config
from server.core.errors import OpenAIAPIException


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
            message="You must provide a valid API key in the Authorization header using 'Bearer <api_key>' format.",
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


def check_ws_handshake_auth(ws: WebSocket) -> tuple[bool, bool]:
    """检查 WebSocket 握手阶段是否携带凭证及凭证是否有效。
    返回: (has_credential, is_valid)
    """
    auth_header = ws.headers.get("authorization", "")
    key = ""
    if auth_header.startswith("Bearer "):
        key = auth_header[7:].strip()
    elif "api_key" in ws.query_params:
        key = ws.query_params.get("api_key", "")

    if not key:
        return False, False
    return True, verify_api_key(key)


def verify_ws_api_key(ws: WebSocket) -> bool:
    """验证 WebSocket 握手阶段的 API Key 是否有效。"""
    has_cred, is_valid = check_ws_handshake_auth(ws)
    return has_cred and is_valid
