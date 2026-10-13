"""OneASR 扩展服务信息 API 契约测试 (GET /v1/x/info)。"""

import pytest

pytestmark = pytest.mark.api


def test_service_info_endpoint(client, auth_headers):
    """测试 GET /v1/x/info 返回服务名、应用版本与 API 版本。"""
    resp = client.get("/v1/x/info", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "OneASR"
    assert "app_version" in data
    assert "api_version" in data
    assert data["status"] == "ok"
