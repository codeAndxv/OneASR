"""OneASR 系统宿主与运维管理 API 契约测试 (/v1/system)。"""

import pytest


def test_system_info(client, auth_headers):
    """测试 GET /v1/system/info 返回硬件与宿主状态。"""
    resp = client.get("/v1/system/info", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "OneASR"
    assert data["status"] == "ok"
    assert "app_version" in data
    assert "api_version" in data
    assert "lan_ip" in data
    assert "uptime_seconds" in data
    assert "hardware" in data
    assert "storage" in data
    assert "platform" in data


def test_system_settings_read_write(client, auth_headers):
    """测试 GET 与 POST /v1/system/settings。"""
    # 读
    resp = client.get("/v1/system/settings", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "port" in data
    assert "lan_ip" in data

    # 写
    update_resp = client.post(
        "/v1/system/settings",
        json={"vad_threshold": 0.65},
        headers=auth_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "updated"
    assert update_resp.json()["saved_settings"]["vad_threshold"] == 0.65


def test_system_open_path(client, auth_headers):
    """测试 POST /v1/system/open-path 正常解析。"""
    resp = client.post(
        "/v1/system/open-path",
        json={"path": "models"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_system_check_update(client, auth_headers):
    """测试 GET /v1/system/check-update。"""
    resp = client.get("/v1/system/check-update", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "current_version" in data
    assert "has_update" in data
