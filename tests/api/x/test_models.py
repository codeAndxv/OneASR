"""OneASR 扩展模型能力矩阵与生命周期 API 契约测试 (/v1/x/models)。"""

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.api


class TestExtendedModelsEndpoint:
    """测试 /v1/x/models 扩展端点。"""

    def test_extended_models_endpoint(self, client, auth_headers):
        """测试 GET /v1/x/models 返回完整能力矩阵与内存状态。"""
        resp = client.get("/v1/x/models", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert "api_version" in data
        assert "data" in data

        for m in data["data"]:
            assert "loaded" in m
            assert "active_tasks" in m
            assert "keep_alive" in m
            assert "languages" in m
            assert "categories" in m
            assert "features" in m

    def test_retrieve_extended_model(self, client, auth_headers):
        """测试 GET /v1/x/models/{model_id}。"""
        resp = client.get("/v1/x/models/whisper-medium", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "whisper-medium"
        assert "languages" in data
        assert "categories" in data

    def test_manual_load_and_unload_model_endpoints(self, client, auth_headers, mock_engine):
        """测试 POST /v1/x/models/{id}/load 与 POST /v1/x/models/{id}/unload。"""
        with patch("server.api.x.models.get_engine", return_value=mock_engine):
            load_resp = client.post("/v1/x/models/whisper-medium/load", headers=auth_headers)
            assert load_resp.status_code == 200
            assert load_resp.json()["id"] == "whisper-medium"
            assert load_resp.json()["status"] == "loaded"

        with patch("server.api.x.models.unload_engine", return_value=True):
            unload_resp = client.post("/v1/x/models/whisper-medium/unload", headers=auth_headers)
            assert unload_resp.status_code == 200
            assert unload_resp.json()["id"] == "whisper-medium"
            assert unload_resp.json()["status"] == "unloaded"
            assert unload_resp.json()["was_loaded"] is True

    def test_unload_busy_model_returns_409(self, client, auth_headers):
        """当模型有活跃任务正在运行时，非强制卸载应返回 409 model_in_use。"""
        with patch("server.api.x.models.unload_engine", side_effect=RuntimeError("模型正在使用中")):
            resp = client.post("/v1/x/models/whisper-medium/unload", headers=auth_headers)
            assert resp.status_code == 409
            assert resp.json()["error"]["code"] == "model_in_use"

    def test_unload_force_parameter_forwarded(self, client, auth_headers):
        """测试 POST /v1/x/models/{id}/unload?force=true 传递 force=True。"""
        with patch("server.api.x.models.unload_engine", return_value=True) as mock_unload:
            resp = client.post(
                "/v1/x/models/whisper-medium/unload?force=true", headers=auth_headers
            )
            assert resp.status_code == 200
            mock_unload.assert_called_once_with("whisper-medium", True)

    def test_load_and_unload_nonexistent_model_returns_404(self, client, auth_headers):
        """对不存在的模型调用 /load 或 /unload 应返回 404 model_not_found。"""
        load_resp = client.post("/v1/x/models/nonexistent-model-xyz/load", headers=auth_headers)
        assert load_resp.status_code == 404
        assert load_resp.json()["error"]["code"] == "model_not_found"

        unload_resp = client.post("/v1/x/models/nonexistent-model-xyz/unload", headers=auth_headers)
        assert unload_resp.status_code == 404
        assert unload_resp.json()["error"]["code"] == "model_not_found"
