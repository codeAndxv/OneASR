"""测试 API 接口的格式参数。"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_formats():
    resp = client.get("/api/v1/formats")
    assert resp.status_code == 200
    data = resp.json()
    assert "formats" in data
    names = [f["name"] for f in data["formats"]]
    assert "text" in names
    assert "srt" in names
    assert "vtt" in names
    assert "json" in names
    assert "tsv" in names


def test_list_engines():
    resp = client.get("/api/v1/engines")
    assert resp.status_code == 200
    data = resp.json()
    assert "default" in data
    assert "engines" in data


def test_transcribe_file_no_engine():
    """没有文件时应该返回 422。"""
    resp = client.post("/api/v1/transcribe/file")
    assert resp.status_code == 422


def test_transcribe_url_invalid():
    """无效 URL 应该返回 400。"""
    resp = client.post(
        "/api/v1/transcribe/url",
        json={"url": "http://invalid.example.com/test.mp3"},
    )
    assert resp.status_code == 400


def test_transcribe_url_invalid_engine():
    """无效引擎名称应该返回错误。"""
    resp = client.post(
        "/api/v1/transcribe/url",
        json={"url": "http://example.com/test.mp3", "engine": "invalid"},
    )
    assert resp.status_code in [400, 500]


if __name__ == "__main__":
    test_list_formats()
    test_list_engines()
    test_transcribe_file_no_engine()
    test_transcribe_url_invalid()
    test_transcribe_url_invalid_engine()
    print("所有 API 测试通过")
