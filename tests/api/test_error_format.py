"""Test OpenAI-compatible error response formats.

Spec: https://developers.openai.com/api/docs/guides/error-codes
"""

import io
import pytest
from fastapi.testclient import TestClient


def test_401_missing_auth_header(client: TestClient):
    """缺少 Authorization header 应该返回 401 authentication_error。"""
    resp = client.get("/v1/models")
    assert resp.status_code == 401
    data = resp.json()

    assert "error" in data
    err = data["error"]
    assert err["type"] == "authentication_error"
    assert err["code"] == "invalid_api_key"
    assert "Authorization" in err["message"] or "API key" in err["message"]


def test_401_invalid_bearer_key(client: TestClient):
    """错误的 API Key 应该返回 401 authentication_error。"""
    resp = client.get("/v1/models", headers={"Authorization": "Bearer wrong-key-12345"})
    assert resp.status_code == 401
    data = resp.json()

    assert "error" in data
    err = data["error"]
    assert err["type"] == "authentication_error"
    assert err["code"] == "invalid_api_key"
    assert "Incorrect API key" in err["message"]


def test_400_file_too_large(client: TestClient):
    """上传超过 25MB 的文件应该返回 400 invalid_request_error，param='file', code='file_too_large'。"""
    large_content = b"\x00" * (25 * 1024 * 1024 + 1)
    files = {"file": ("large_test.wav", io.BytesIO(large_content), "audio/wav")}

    resp = client.post(
        "/v1/audio/transcriptions",
        headers={"Authorization": "Bearer oneasr-key"},
        files=files,
        data={"model": "whisper1"},
    )
    assert resp.status_code == 400
    data = resp.json()

    assert "error" in data
    err = data["error"]
    assert err["type"] == "invalid_request_error"
    assert err["param"] == "file"
    assert err["code"] == "file_too_large"
    assert "25MB" in err["message"] or "超过限制" in err["message"]


def test_400_validation_error(client: TestClient):
    """请求缺少必填参数时应该返回 400 validation_error 并指出 param。"""
    resp = client.post(
        "/v1/audio/transcriptions",
        headers={"Authorization": "Bearer oneasr-key"},
        # 故意不传 file 和 model
        data={},
    )
    assert resp.status_code == 400
    data = resp.json()

    assert "error" in data
    err = data["error"]
    assert err["type"] == "invalid_request_error"
    assert err["code"] == "validation_error"
    assert err["param"] is not None


def test_404_model_not_found(client: TestClient):
    """请求不存在的模型时应该返回 404 invalid_request_error, code='model_not_found', param='model'。"""
    resp = client.get("/v1/models/non_existent_model_xyz", headers={"Authorization": "Bearer oneasr-key"})
    assert resp.status_code == 404
    data = resp.json()

    assert "error" in data
    err = data["error"]
    assert err["type"] == "invalid_request_error"
    assert err["code"] == "model_not_found"
    assert err["param"] == "model"
    assert "non_existent_model_xyz" in err["message"]


def test_404_route_not_found(client: TestClient):
    """请求不存在的路径应该返回 404 invalid_request_error。"""
    resp = client.get("/v1/non_existent_route", headers={"Authorization": "Bearer oneasr-key"})
    assert resp.status_code == 404
    data = resp.json()

    assert "error" in data
    err = data["error"]
    assert err["type"] == "invalid_request_error"
    assert err["code"] == "resource_not_found"
