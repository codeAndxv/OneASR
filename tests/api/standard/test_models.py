"""OpenAI 标准模型查询接口契约测试 (GET /v1/models, GET /v1/models/{model_id})。"""

import pytest

pytestmark = pytest.mark.api


class TestOpenAIModelsEndpoint:
    """测试 /v1/models 端点。"""

    def test_list_models_success(self, client, auth_headers):
        """列出可用模型（标准 OpenAI 格式）。"""
        resp = client.get("/v1/models", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert "data" in data
        assert len(data["data"]) > 0

        model = data["data"][0]
        assert "id" in model
        assert model["object"] == "model"
        assert "created" in model
        assert "owned_by" in model
        assert "loaded" in model

    def test_list_models_without_api_key(self, client):
        """未提供 API Key 应该返回 401 authentication_error。"""
        resp = client.get("/v1/models")
        assert resp.status_code == 401
        data = resp.json()
        assert "error" in data
        assert data["error"]["type"] == "authentication_error"

    def test_retrieve_model_success(self, client, auth_headers):
        """查询已存在的单个模型详情。"""
        resp = client.get("/v1/models/whisper-medium", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "whisper-medium"
        assert data["object"] == "model"
        assert "loaded" in data

    def test_retrieve_nonexistent_model(self, client, auth_headers):
        """查询不存在的模型应返回 404 model_not_found。"""
        resp = client.get("/v1/models/nonexistent-model-xyz", headers=auth_headers)
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "model_not_found"
