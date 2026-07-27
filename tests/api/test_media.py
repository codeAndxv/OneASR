"""媒体 URL 异步下载 API 测试。

全程 mock yt-dlp，不发真实网络请求 —— 真实站点测试见
tests/general/ 下打 @pytest.mark.integration 标记的用例。

鉴权沿用 app/api/auth.py 实际定义的 Authorization: Bearer。
async 测试采用项目惯有范式：async 助手 + asyncio.run 包裹（项目无 pytest-asyncio）。
"""

import asyncio
from unittest.mock import patch

import pytest

AUTH = {"Authorization": "Bearer oneasr-key"}


# ── 工具：mock yt-dlp 让 _run_download 快速收敛 ─────────────────────

def _make_video_info():
    from app.utils.video_url import VideoInfo
    return VideoInfo(
        title="mock title",
        duration_seconds=120,
        uploader="mock_uploader",
        extractor="Mock",
    )


def _patch_yt_dlp_success(tmp_download_path: str):
    """patch yt-dlp 的下载与解析，使后台任务快速成功。

    返回 dict: name -> patcher，调用方用 .start()/.stop() 控制。
    """
    def _fake_download_video(url, *, audio_only, progress_hook=None, max_filesize_bytes=None):
        if progress_hook:
            progress_hook({"status": "downloading",
                           "downloaded_bytes": 50, "total_bytes": 100})
            progress_hook({"status": "finished"})
        return _make_video_info(), tmp_download_path, 1024

    def _fake_extract_info(url):
        return _make_video_info()

    return {
        "download_video": patch("app.services.media_service.download_video",
                                side_effect=_fake_download_video),
        "extract_info": patch("app.services.media_service.extract_info",
                              side_effect=_fake_extract_info),
    }


async def _wait_until_terminal(task_id: str, timeout_s: float = 1.0) -> str | None:
    """轮询任务直到收敛到 succeeded/failed，返回最终状态。"""
    for _ in range(int(timeout_s / 0.05)):
        from app.services import media_service
        r = await media_service.get_task(task_id)
        if r and r.status in ("succeeded", "failed"):
            return r.status
        await asyncio.sleep(0.05)
    return None


# ── tests ────────────────────────────────────────────────────────────

class TestMediaParse:
    """媒体 URL 解析端点测试（同步端点部分）"""

    def test_parse_requires_auth(self, client):
        """无鉴权应被拒"""
        resp = client.post("/v1/media/parse", json={"url": "https://www.youtube.com/watch?v=abc"})
        assert resp.status_code in (401, 403, 422)

    def test_parse_rejects_empty_url(self, client):
        """空 url 应 422/400"""
        resp = client.post("/v1/media/parse", json={"url": ""}, headers=AUTH)
        assert resp.status_code in (400, 422)

    def test_parse_rejects_bad_format(self, client):
        """非法 format 应 400"""
        resp = client.post(
            "/v1/media/parse",
            json={"url": "https://www.youtube.com/watch?v=abc", "format": "mp4"},
            headers=AUTH,
        )
        assert resp.status_code == 400
        assert "format" in resp.json()["detail"]

    @pytest.mark.parametrize("url,expected_platform", [
        ("https://www.douyin.com/video/123", "douyin"),
        ("https://v.douyin.com/abc123/", "douyin"),
        ("https://www.tiktok.com/@user/video/123", "tiktok"),
        ("https://www.bilibili.com/video/BV1abc", "bilibili"),
        ("https://b23.tv/abc", "bilibili"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube"),
        ("https://youtu.be/abc", "youtube"),
        ("https://example.com/somewhere", "unknown"),
    ])
    def test_platform_detection_via_parse(self, client, url, expected_platform):
        """提交 URL 应正确识别平台并返回 task_id（mock 后台起任务）。"""
        with patch("app.services.media_service.create_parse_task",
                   return_value="mock-task-id") as m:
            resp = client.post("/v1/media/parse", json={"url": url, "format": "audio"}, headers=AUTH)

        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "mock-task-id"
        assert data["status"] == "pending"
        assert data["platform"] == expected_platform
        m.assert_awaited_once_with(url, "audio")

    def test_parse_invalid_url_field_missing(self, client):
        """缺 url 字段应 422"""
        resp = client.post("/v1/media/parse", json={"format": "audio"}, headers=AUTH)
        assert resp.status_code == 422


class TestMediaTaskQueryAndDelete:
    """任务查询与删除"""

    def test_get_task_not_found(self, client):
        async def _run():
            from app.services import media_service
            r = await media_service.get_task("nonexistent-id")
            return r
        asyncio.run(_run())
        resp = client.get("/v1/media/parse/nonexistent-id", headers=AUTH)
        assert resp.status_code == 404

    def test_delete_task_not_found(self, client):
        resp = client.delete("/v1/media/parse/nonexistent-id", headers=AUTH)
        assert resp.status_code == 404

    def test_list_tasks_empty(self, client):
        resp = client.get("/v1/media/parse", headers=AUTH)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["tasks"] == []

    def test_create_and_query_and_delete_task(self, client, tmp_path):
        """端到端：创建(mock快速成功) → 查询 → 删除。

        create/wait 必须在同一个事件循环里跑：后台 _run_download 协程依附于
        create_parse_task 所在的循环，循环一关协程即早夭。故把 create + wait
        合并到一个 async 体内通过单次 asyncio.run 执行。
        """
        async def _setup_and_wait():
            from app.services import media_service
            task_id = await media_service.create_parse_task(
                "https://www.youtube.com/watch?v=abc", "audio"
            )
            final = await _wait_until_terminal(task_id)
            return task_id, final

        async def _get(tid):
            from app.services import media_service
            return await media_service.get_task(tid)

        async def _list():
            from app.services import media_service
            return await media_service.list_tasks()

        async def _del(tid):
            from app.services import media_service
            return await media_service.delete_task(tid)

        fake_file = tmp_path / "fake.mp3"
        fake_file.write_bytes(b"fake audio bytes")

        patchers = _patch_yt_dlp_success(str(fake_file))
        for p in patchers.values():
            p.start()
        try:
            task_id, final = asyncio.run(_setup_and_wait())
            assert final == "succeeded", f"expected succeeded, got {final}"

            r = asyncio.run(_get(task_id))
            assert r is not None
            assert r.status == "succeeded", f"err={r.error_message}"
            assert r.title == "mock title"
            assert r.duration_seconds == 120
            assert r.file_path == str(fake_file)
            assert r.file_size == 1024
            assert r.platform == "youtube"

            records = asyncio.run(_list())
            assert len(records) == 1
            assert records[0].id == task_id

            resp = client.get(f"/v1/media/parse/{task_id}", headers=AUTH)
            assert resp.status_code == 200
            body = resp.json()
            assert body["task_id"] == task_id
            assert body["status"] == "succeeded"
            assert body["platform"] == "youtube"

            resp = client.delete(f"/v1/media/parse/{task_id}", headers=AUTH)
            assert resp.status_code == 200
            assert "已删除" in resp.json()["message"]

            r = asyncio.run(_get(task_id))
            assert r is None
            assert not fake_file.exists(), "DELETE 应连带删 download/ 下文件"
        finally:
            for p in patchers.values():
                p.stop()


class TestMediaFileDownload:
    """下载已完成文件到客户端"""

    def test_download_file_not_succeeded(self, client):
        """非 succeeded 状态下载返回 409"""
        async def _create():
            from app.services import media_service
            return await media_service.create_parse_task(
                "https://www.youtube.com/watch?v=xyz", "audio"
            )
        task_id = asyncio.run(_create())
        # 不等后台跑完，立即查询（仍可能 pending/running）
        resp = client.get(f"/v1/media/parse/{task_id}/file", headers=AUTH)
        assert resp.status_code in (404, 409)

    def test_download_file_success(self, client, tmp_path):
        """succeeded 后下载应返回文件流"""
        async def _create_and_wait():
            from app.services import media_service
            task_id = await media_service.create_parse_task(
                "https://www.bilibili.com/video/BV1xx", "video"
            )
            final = await _wait_until_terminal(task_id)
            return task_id, final
        fake_file = tmp_path / "done.mp4"
        fake_file.write_bytes(b"video bytes here")

        patchers = _patch_yt_dlp_success(str(fake_file))
        for p in patchers.values():
            p.start()
        try:
            task_id, final = asyncio.run(_create_and_wait())
            assert final == "succeeded"

            resp = client.get(f"/v1/media/parse/{task_id}/file", headers=AUTH)
            assert resp.status_code == 200
            assert resp.content == b"video bytes here"
            cd = resp.headers.get("content-disposition", "")
            assert "bilibili" in cd.lower() or "mock" in cd.lower()
        finally:
            for p in patchers.values():
                p.stop()
