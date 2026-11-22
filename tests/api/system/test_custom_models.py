"""Unit and API tests for custom model registration, validation, and lifecycle (/v1/system/custom-models)."""

from pathlib import Path
import pytest


def test_custom_model_validation_failures(client, auth_headers, tmp_path):
    """Test validation errors on invalid ID, non-existent path, or missing weights."""
    # 1. Invalid ID with illegal characters
    resp = client.post(
        "/v1/system/custom-models",
        json={"id": "my model@bad!", "driver": "xasr", "model_path": str(tmp_path)},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "alphanumeric" in resp.json()["detail"]

    # 2. Conflicting with builtin model ID
    resp = client.post(
        "/v1/system/custom-models",
        json={"id": "xasr-zh-en-160ms", "driver": "xasr", "model_path": str(tmp_path)},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "conflicts with a built-in model" in resp.json()["detail"]

    # 3. Non-existent path
    resp = client.post(
        "/v1/system/custom-models",
        json={"id": "valid-custom-1", "driver": "xasr", "model_path": "/path/does/not/exist/999"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "Directory does not exist" in resp.json()["detail"]

    # 4. Driver missing required files (xasr requires tokens.txt and encoder*.onnx)
    dummy_dir = tmp_path / "empty_model"
    dummy_dir.mkdir()
    resp = client.post(
        "/v1/system/custom-models",
        json={"id": "valid-custom-1", "driver": "xasr", "model_path": str(dummy_dir)},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "tokens.txt" in resp.json()["detail"]


def test_custom_model_full_lifecycle(client, auth_headers, tmp_path):
    """Test registering, listing, protecting against rmtree deletion, and unregistering a custom model."""
    # 1. Prepare a mock custom xasr model directory
    mock_model_dir = tmp_path / "mock_sherpa_custom"
    mock_model_dir.mkdir()
    (mock_model_dir / "tokens.txt").write_text("hello 1\nworld 2\n")
    (mock_model_dir / "encoder.onnx").write_bytes(b"dummy onnx bytes")

    # 2. Register
    resp = client.post(
        "/v1/system/custom-models",
        json={
            "id": "test-mock-sherpa",
            "name": "Mock Sherpa Custom",
            "driver": "xasr",
            "model_path": str(mock_model_dir),
            "languages": ["zh", "en"],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "registered"

    # 3. GET /v1/system/custom-models
    list_resp = client.get("/v1/system/custom-models", headers=auth_headers)
    assert list_resp.status_code == 200
    custom_ids = [m["id"] for m in list_resp.json()["custom_models"]]
    assert "test-mock-sherpa" in custom_ids

    # 4. Catalog listing includes it with is_custom=True
    cat_resp = client.get("/v1/x/models?all=true", headers=auth_headers)
    assert cat_resp.status_code == 200
    items = {m["id"]: m for m in cat_resp.json()["data"]}
    assert "test-mock-sherpa" in items
    assert items["test-mock-sherpa"]["is_custom"] is True
    assert items["test-mock-sherpa"]["status"] == "ready"

    # 5. Verify DELETE /v1/x/models/{id} refuses to delete custom model to prevent data loss
    del_forbidden_resp = client.delete("/v1/x/models/test-mock-sherpa", headers=auth_headers)
    assert del_forbidden_resp.status_code == 400
    assert "custom registered model" in del_forbidden_resp.json()["error"]["message"]
    # Verify disk files were NOT deleted
    assert (mock_model_dir / "tokens.txt").exists()

    # 6. Unregister custom model safely via /v1/system/custom-models/{id}
    unreg_resp = client.delete("/v1/system/custom-models/test-mock-sherpa", headers=auth_headers)
    assert unreg_resp.status_code == 200
    assert unreg_resp.json()["status"] == "unregistered"

    # Verify disk files still exist after unregistering
    assert (mock_model_dir / "tokens.txt").exists()

    # 7. Unregister non-existent returns 404
    unreg_404 = client.delete("/v1/system/custom-models/test-mock-sherpa", headers=auth_headers)
    assert unreg_404.status_code == 404
