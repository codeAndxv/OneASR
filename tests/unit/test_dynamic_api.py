"""Unit tests for Ollama-style dynamic model pull/cancel/delete and system diagnostics APIs."""

import json
import pytest
from starlette.testclient import TestClient

from server.core.manifest import BUILTIN_MODELS
from server.main import app

pytestmark = pytest.mark.unit


def test_list_extended_models(client, auth_headers):
    """Verify that GET /v1/x/models returns all catalog models with real-time status."""
    response = client.get("/v1/x/models", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert "data" in data

    model_ids = [m["id"] for m in data["data"]]
    # Verify core built-in models exist in the catalog listing
    assert "sensevoice-small" in model_ids
    assert "whisper-large-v3-turbo" in model_ids
    assert "xasr-zh-en" in model_ids

    # Verify status fields exist on every item
    for item in data["data"]:
        assert "status" in item
        assert item["status"] in ("ready", "not_downloaded", "downloading", "corrupted")
        assert "size_on_disk" in item
        assert "size_expected" in item


def test_retrieve_single_extended_model(client, auth_headers):
    """Verify that GET /v1/x/models/{model_id} resolves canonical models and aliases."""
    # Test canonical ID
    res1 = client.get("/v1/x/models/sensevoice-small", headers=auth_headers)
    assert res1.status_code == 200
    assert res1.json()["id"] == "sensevoice-small"

    # Test alias resolution (sensevoice -> sensevoice-small)
    res2 = client.get("/v1/x/models/sensevoice", headers=auth_headers)
    assert res2.status_code == 200
    assert res2.json()["id"] == "sensevoice-small"

    # Test unknown model returns 404
    res3 = client.get("/v1/x/models/non-existent-xyz-999", headers=auth_headers)
    assert res3.status_code == 404


def test_system_info_endpoint(client, auth_headers):
    """Verify that GET /v1/x/system/info returns platform, hardware, accelerator, and storage stats."""
    response = client.get("/v1/x/system/info", headers=auth_headers)
    assert response.status_code == 200
    info = response.json()

    assert info["service"] == "OneASR"
    assert "uptime_seconds" in info
    assert "platform" in info
    assert "hardware" in info
    assert "storage" in info

    # Verify accelerator detection fields
    assert "accelerator" in info["hardware"]
    assert info["hardware"]["accelerator"] in ("cuda", "mps", "cpu")
    assert "device_name" in info["hardware"]
    assert "ram_total_mb" in info["hardware"]


def test_system_settings_get_and_update(client, auth_headers, tmp_path, monkeypatch):
    """Verify that GET/POST /v1/x/system/settings reads and updates preferences atomically."""
    fake_home = tmp_path / "fake_home"
    monkeypatch.setenv("ONEASR_HOME", str(fake_home))

    # Read current settings
    get_res = client.get("/v1/x/system/settings", headers=auth_headers)
    assert get_res.status_code == 200
    settings_data = get_res.json()
    assert "default_keep_alive" in settings_data

    # Update settings
    post_res = client.post(
        "/v1/x/system/settings",
        json={"default_model": "whisper-large-v3-turbo", "keep_alive": 1200},
        headers=auth_headers,
    )
    assert post_res.status_code == 200
    assert post_res.json()["status"] == "updated"
    assert post_res.json()["saved_settings"]["default_model"] == "whisper-large-v3-turbo"
    assert post_res.json()["saved_settings"]["keep_alive"] == 1200


def test_cancel_non_active_pull(client, auth_headers):
    """Verify that cancelling a non-active download returns not_active."""
    res = client.post("/v1/x/models/cancel", json={"model_id": "sensevoice-small"}, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["cancelled"] is False


def test_pull_model_unknown_returns_404(client, auth_headers):
    """Verify that attempting to pull an unknown model returns 404."""
    res = client.post("/v1/x/models/pull", json={"model_id": "totally-fake-model-123"}, headers=auth_headers)
    assert res.status_code == 404
