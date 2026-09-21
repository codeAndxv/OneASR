"""Tests for /v1/file/transcriptions JSON task creation endpoint."""

import pytest
from fastapi.testclient import TestClient


def test_create_task_missing_both_sources(client: TestClient):
    """缺少 file_uuid 和 file_url 应该返回 400。"""
    resp = client.post(
        "/v1/file/transcriptions",
        headers={"Authorization": "Bearer oneasr-key"},
        json={"model": "whisper1"},
    )
    assert resp.status_code == 400
    data = resp.json()
    assert "Must provide either file_uuid or file_url" in str(data)


def test_create_task_nonexistent_uuid(client: TestClient):
    """传入不存在的 file_uuid 应该返回 404。"""
    resp = client.post(
        "/v1/file/transcriptions",
        headers={"Authorization": "Bearer oneasr-key"},
        json={
            "file_uuid": "nonexistent-uuid-12345",
            "model": "whisper1",
            "language": "en",
        },
    )
    assert resp.status_code == 404
    data = resp.json()
    assert "File not found" in str(data)
