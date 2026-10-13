"""文件上传和管理 API 测试 (OneASR Extended /v1/x/files，含 MD5 秒传)。"""

import hashlib
import io

import pytest

pytestmark = pytest.mark.api


def _md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


class TestFileUpload:
    """文件上传测试"""

    def test_upload_file_success(self, client, auth_headers):
        """测试成功上传文件"""
        test_content = b"fake audio content"
        files = {"file": ("test.mp3", io.BytesIO(test_content), "audio/mpeg")}

        response = client.post(
            "/v1/x/files",
            files=files,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "file_id" in data
        assert data["filename"] == "test.mp3"
        assert data["file_size"] == len(test_content)
        assert data["file_md5"] == _md5(test_content)
        assert data["duplicate"] is False

    def test_upload_file_unsupported_format(self, client, auth_headers):
        """测试上传不支持的文件格式"""
        test_content = b"fake content"
        files = {"file": ("test.txt", io.BytesIO(test_content), "text/plain")}

        response = client.post(
            "/v1/x/files",
            files=files,
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "Unsupported file format" in response.json()["detail"] or "不支持" in response.json()["detail"]

    def test_upload_file_no_auth(self, client):
        """测试无认证上传文件"""
        test_content = b"fake audio content"
        files = {"file": ("test.mp3", io.BytesIO(test_content), "audio/mpeg")}

        response = client.post("/v1/x/files", files=files)
        assert response.status_code in [401, 403, 422]

    def test_upload_file_size_mismatch(self, client, auth_headers):
        """测试 file_size 参数与实际不匹配"""
        test_content = b"fake audio content"
        md5 = _md5(test_content)
        files = {"file": ("test.mp3", io.BytesIO(test_content), "audio/mpeg")}

        response = client.post(
            f"/v1/x/files?file_md5={md5}&file_size=999999",
            files=files,
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "file_size" in response.json()["detail"]

    def test_upload_duplicate_md5_instant_upload(self, client, auth_headers):
        """测试秒传：相同 MD5 + 大小的文件返回已有 file_id"""
        test_content = b"exact same audio content for dedup test"
        md5 = _md5(test_content)
        size = len(test_content)

        files1 = {"file": ("dedup.mp3", io.BytesIO(test_content), "audio/mpeg")}
        resp1 = client.post("/v1/x/files", files=files1, headers=auth_headers)
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["duplicate"] is False

        files2 = {"file": ("dedup_copy.mp3", io.BytesIO(test_content), "audio/mpeg")}
        resp2 = client.post(
            f"/v1/x/files?file_md5={md5}&file_size={size}",
            files=files2,
            headers=auth_headers,
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["duplicate"] is True
        assert data2["file_id"] == data1["file_id"]
        assert data2["file_md5"] == md5


class TestFileList:
    """文件列表测试"""

    def test_list_files(self, client, auth_headers):
        response = client.get("/v1/x/files", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert "total" in data
        assert isinstance(data["files"], list)

    def test_list_files_no_auth(self, client):
        response = client.get("/v1/x/files")
        assert response.status_code in [401, 403, 422]


class TestFileDelete:
    """文件删除测试"""

    def test_delete_file_success(self, client, auth_headers):
        test_content = b"fake audio content"
        files = {"file": ("test_delete.mp3", io.BytesIO(test_content), "audio/mpeg")}

        upload_response = client.post("/v1/x/files", files=files, headers=auth_headers)
        assert upload_response.status_code == 200
        file_id = upload_response.json()["file_id"]

        response = client.delete(f"/v1/x/files/{file_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "File deleted successfully"

    def test_delete_file_not_found(self, client, auth_headers):
        response = client.delete("/v1/x/files/nonexistent-id", headers=auth_headers)
        assert response.status_code == 404
        assert "File not found" in response.json()["detail"] or "文件不存在" in response.json()["detail"]

    def test_delete_file_no_auth(self, client):
        response = client.delete("/v1/x/files/some-id")
        assert response.status_code in [401, 403, 422]


class TestFileInfo:
    """文件信息测试"""

    def test_get_file_info_success(self, client, auth_headers):
        test_content = b"fake audio content"
        files = {"file": ("test_info.mp3", io.BytesIO(test_content), "audio/mpeg")}

        upload_response = client.post("/v1/x/files", files=files, headers=auth_headers)
        assert upload_response.status_code == 200
        file_id = upload_response.json()["file_id"]

        response = client.get(f"/v1/x/files/{file_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["file_id"] == file_id
        assert data["filename"] == "test_info.mp3"

    def test_get_file_info_not_found(self, client, auth_headers):
        response = client.get("/v1/x/files/nonexistent-id", headers=auth_headers)
        assert response.status_code == 404
        assert "File not found" in response.json()["detail"] or "文件不存在" in response.json()["detail"]
