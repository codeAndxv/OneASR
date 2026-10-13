"""Tests for /v1/x/audio/transcriptions async task lifecycle endpoints."""

import io
import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server.db import async_session
from server.db.orm_models import TranscriptionSegment, TranscriptionTask

pytestmark = pytest.mark.api


def _upload_test_wav(client: TestClient, auth_headers: dict, wav_bytes: bytes) -> str:
    resp = client.post(
        "/v1/x/files",
        headers=auth_headers,
        files={"file": ("sample.wav", io.BytesIO(wav_bytes), "audio/wav")},
    )
    assert resp.status_code == 200
    return resp.json()["file_id"]


def test_create_task_missing_both_sources(client: TestClient, auth_headers: dict):
    """缺少 file_uuid 应该返回 400。"""
    resp = client.post(
        "/v1/x/audio/transcriptions",
        headers=auth_headers,
        json={"model": "faster-whisper"},
    )
    assert resp.status_code == 400
    data = resp.json()
    assert "file_uuid" in str(data)


def test_create_task_nonexistent_uuid(client: TestClient, auth_headers: dict):
    """传入不存在的 file_uuid 应该返回 404。"""
    resp = client.post(
        "/v1/x/audio/transcriptions",
        headers=auth_headers,
        json={
            "file_uuid": "nonexistent-uuid-12345",
            "model": "faster-whisper",
            "language": "en",
        },
    )
    assert resp.status_code == 404
    data = resp.json()
    assert "File not found" in str(data)


def test_create_and_query_task_lifecycle(
    client: TestClient, auth_headers: dict, wav_bytes: bytes, mock_engine
):
    """完整测试：上传 WAV -> 创建转录任务 -> 查询任务状态 -> 查询任务列表。"""
    file_id = _upload_test_wav(client, auth_headers, wav_bytes)

    with patch("server.services.transcription_service.get_engine", return_value=mock_engine):
        create_resp = client.post(
            "/v1/x/audio/transcriptions",
            headers=auth_headers,
            json={
                "file_uuid": file_id,
                "model": "faster-whisper",
                "language": "zh",
                "response_format": "json",
            },
        )
        assert create_resp.status_code == 200
        task_id = create_resp.json()["task_id"]

        # 查询任务详情
        status_resp = client.get(f"/v1/x/audio/transcriptions/{task_id}", headers=auth_headers)
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["task_id"] == task_id
        assert status_data["status"] in ("pending", "processing", "completed")

        # 查询任务列表
        list_resp = client.get("/v1/x/audio/transcriptions", headers=auth_headers)
        assert list_resp.status_code == 200
        list_data = list_resp.json()
        assert list_data["total"] >= 1
        assert any(t["task_id"] == task_id for t in list_data["tasks"])


def test_get_task_not_found(client: TestClient, auth_headers: dict):
    """查询不存在的 task_id 返回 404。"""
    resp = client.get("/v1/x/audio/transcriptions/nonexistent-task", headers=auth_headers)
    assert resp.status_code == 404


async def test_stream_completed_task_sse(client: TestClient, auth_headers: dict):
    """测试已完成任务的 SSE 流式端点 (/v1/x/audio/transcriptions/{task_id}/stream)。"""
    task_id = "test-completed-task-001"
    now = datetime.now(timezone.utc)

    async with async_session() as s:
        s.add(
            TranscriptionTask(
                task_id=task_id,
                status="completed",
                progress=1.0,
                source_type="file_uuid",
                filename="sample.wav",
                file_size=32044,
                file_uuid="fake-uuid",
                model="faster-whisper",
                language="zh",
                response_format="json",
                result_text="你好，测试语音转录。",
                result_duration=1.0,
                segment_count=1,
                created_at=now,
                updated_at=now,
                completed_at=now,
            )
        )
        s.add(
            TranscriptionSegment(
                task_id=task_id,
                segment_index=0,
                start=0.0,
                end=1.0,
                text="你好，测试语音转录。",
            )
        )
        await s.commit()

    resp = client.get(f"/v1/x/audio/transcriptions/{task_id}/stream", headers=auth_headers)
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    events = [
        json.loads(line[len("data: "):])
        for line in resp.text.strip().split("\n")
        if line.strip().startswith("data: ")
    ]
    assert len(events) == 2
    assert events[0]["type"] == "transcript.text.delta"
    assert events[0]["delta"] == "你好，测试语音转录。"
    assert events[1]["type"] == "transcript.text.done"


async def test_cancel_pending_task(client: TestClient, auth_headers: dict):
    """测试取消 pending 状态的任务 (DELETE /v1/x/audio/transcriptions/{task_id})。"""
    task_id = "test-pending-task-002"
    now = datetime.now(timezone.utc)

    async with async_session() as s:
        s.add(
            TranscriptionTask(
                task_id=task_id,
                status="pending",
                progress=0.0,
                source_type="file_uuid",
                filename="sample.wav",
                model="faster-whisper",
                created_at=now,
                updated_at=now,
            )
        )
        await s.commit()

    del_resp = client.delete(f"/v1/x/audio/transcriptions/{task_id}", headers=auth_headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["task_id"] == task_id

    # 再次取消已 cancelled 的任务应返回 400
    del_again = client.delete(f"/v1/x/audio/transcriptions/{task_id}", headers=auth_headers)
    assert del_again.status_code == 400
