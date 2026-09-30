"""OpenAI-compatible error handling definitions and utilities.

Spec: https://developers.openai.com/api/docs/guides/error-codes
"""

from typing import Any, Optional
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class OpenAIErrorObject(BaseModel):
    message: str = Field(..., description="A human-readable message providing more details about the error.")
    type: str = Field(..., description="The type of error (e.g. invalid_request_error, authentication_error, api_error).")
    param: Optional[str] = Field(None, description="The parameter that caused the error, if applicable.")
    code: Optional[str] = Field(None, description="The specific error code (e.g. invalid_api_key, file_too_large).")


class OpenAIErrorResponse(BaseModel):
    error: OpenAIErrorObject
    detail: Optional[Any] = Field(None, description="FastAPI-compatible detail field for backward compatibility.")


def get_default_error_type(status_code: int) -> str:
    """根据 HTTP 状态码推导 OpenAI 标准 error type。"""
    if status_code == 401:
        return "authentication_error"
    elif status_code == 403:
        return "permission_error"
    elif status_code == 429:
        return "rate_limit_error"
    elif status_code == 503:
        return "service_unavailable_error"
    elif status_code >= 500:
        return "api_error"
    else:
        return "invalid_request_error"


def get_default_error_code(status_code: int) -> Optional[str]:
    """根据 HTTP 状态码推导默认 error code。"""
    mapping = {
        400: "bad_request",
        401: "invalid_api_key",
        403: "forbidden",
        404: "resource_not_found",
        422: "validation_error",
        429: "rate_limit_exceeded",
        500: "internal_error",
        503: "service_unavailable",
    }
    return mapping.get(status_code, None)


class OpenAIAPIException(HTTPException):
    """自定义支持 OpenAI 格式的 API 异常。"""

    def __init__(
        self,
        status_code: int,
        message: str,
        error_type: Optional[str] = None,
        param: Optional[str] = None,
        code: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
    ):
        self.message = message
        self.error_type = error_type or get_default_error_type(status_code)
        self.param = param
        self.code = code or get_default_error_code(status_code)
        super().__init__(status_code=status_code, detail=message, headers=headers)


def build_openai_error_json_response(
    status_code: int,
    message: str,
    error_type: Optional[str] = None,
    param: Optional[str] = None,
    code: Optional[str] = None,
    raw_detail: Optional[Any] = None,
    headers: Optional[dict[str, str]] = None,
) -> JSONResponse:
    """构建统一符合 OpenAI 规范的 JSONResponse，同时包含 detail 字段保持向后兼容。"""
    err_type = error_type or get_default_error_type(status_code)
    err_code = code if code is not None else get_default_error_code(status_code)
    detail_val = raw_detail if raw_detail is not None else message

    content = {
        "detail": detail_val,
        "error": {
            "message": message,
            "type": err_type,
            "param": param,
            "code": err_code,
        },
    }
    return JSONResponse(status_code=status_code, content=content, headers=headers)
