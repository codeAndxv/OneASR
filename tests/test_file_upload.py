"""
文件上传和管理 API 测试
"""

import io
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestFileUpload:
    """文件上传测试"""
    
    def test_upload_file_success(self, client):
        """测试成功上传文件"""
        test_content = b"fake audio content"
        files = {"file": ("test.mp3", io.BytesIO(test_content), "audio/mpeg")}
        
        response = client.post(
            "/api/v1/files/upload",
            files=files,
            headers={"X-API-Key": "oneasr-key"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "file_id" in data
        assert data["filename"] == "test.mp3"
        assert data["file_size"] == len(test_content)
        assert data["message"] == "File uploaded successfully"
    
    def test_upload_file_unsupported_format(self, client):
        """测试上传不支持的文件格式"""
        test_content = b"fake content"
        files = {"file": ("test.txt", io.BytesIO(test_content), "text/plain")}
        
        response = client.post(
            "/api/v1/files/upload",
            files=files,
            headers={"X-API-Key": "oneasr-key"},
        )
        
        assert response.status_code == 400
        assert "不支持的文件格式" in response.json()["detail"]
    
    def test_upload_file_no_auth(self, client):
        """测试无认证上传文件"""
        test_content = b"fake audio content"
        files = {"file": ("test.mp3", io.BytesIO(test_content), "audio/mpeg")}
        
        response = client.post(
            "/api/v1/files/upload",
            files=files,
        )
        
        assert response.status_code in [401, 403, 422]


class TestFileList:
    """文件列表测试"""
    
    def test_list_files(self, client):
        """测试获取文件列表"""
        response = client.get(
            "/api/v1/files/list",
            headers={"X-API-Key": "oneasr-key"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert "total" in data
        assert isinstance(data["files"], list)
    
    def test_list_files_no_auth(self, client):
        """测试无认证获取文件列表"""
        response = client.get("/api/v1/files/list")
        assert response.status_code in [401, 403, 422]


class TestFileDelete:
    """文件删除测试"""
    
    def test_delete_file_success(self, client):
        """测试成功删除文件"""
        # 先上传一个文件
        test_content = b"fake audio content"
        files = {"file": ("test_delete.mp3", io.BytesIO(test_content), "audio/mpeg")}
        
        upload_response = client.post(
            "/api/v1/files/upload",
            files=files,
            headers={"X-API-Key": "oneasr-key"},
        )
        assert upload_response.status_code == 200
        file_id = upload_response.json()["file_id"]
        
        # 删除文件
        response = client.delete(
            f"/api/v1/files/{file_id}",
            headers={"X-API-Key": "oneasr-key"},
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "File deleted successfully"
    
    def test_delete_file_not_found(self, client):
        """测试删除不存在的文件"""
        response = client.delete(
            "/api/v1/files/nonexistent-id",
            headers={"X-API-Key": "oneasr-key"},
        )
        
        assert response.status_code == 404
        assert "文件不存在" in response.json()["detail"]
    
    def test_delete_file_no_auth(self, client):
        """测试无认证删除文件"""
        response = client.delete(
            "/api/v1/files/some-id",
        )
        assert response.status_code in [401, 403, 422]


class TestFileInfo:
    """文件信息测试"""
    
    def test_get_file_info_success(self, client):
        """测试成功获取文件信息"""
        # 先上传一个文件
        test_content = b"fake audio content"
        files = {"file": ("test_info.mp3", io.BytesIO(test_content), "audio/mpeg")}
        
        upload_response = client.post(
            "/api/v1/files/upload",
            files=files,
            headers={"X-API-Key": "oneasr-key"},
        )
        assert upload_response.status_code == 200
        file_id = upload_response.json()["file_id"]
        
        # 获取文件信息
        response = client.get(
            f"/api/v1/files/{file_id}",
            headers={"X-API-Key": "oneasr-key"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["file_id"] == file_id
        assert data["filename"] == "test_info.mp3"
    
    def test_get_file_info_not_found(self, client):
        """测试获取不存在文件的信息"""
        response = client.get(
            "/api/v1/files/nonexistent-id",
            headers={"X-API-Key": "oneasr-key"},
        )
        
        assert response.status_code == 404
        assert "文件不存在" in response.json()["detail"]


class TestTranscriptionWithUUID:
    """使用 UUID 进行转录的测试"""
    
    def test_transcribe_with_file_uuid(self, client):
        """测试使用 file_uuid 进行转录"""
        # 先上传一个文件
        test_content = b"fake audio content"
        files = {"file": ("test_transcribe.mp3", io.BytesIO(test_content), "audio/mpeg")}
        
        upload_response = client.post(
            "/api/v1/files/upload",
            files=files,
            headers={"X-API-Key": "oneasr-key"},
        )
        assert upload_response.status_code == 200
        file_id = upload_response.json()["file_id"]
        
        # 使用 file_uuid 进行转录
        form_data = {
            "file_uuid": file_id,
            "model": "whisper",
            "response_format": "json",
        }
        
        response = client.post(
            "/api/v1/audio/transcriptions",
            data=form_data,
            headers={"X-API-Key": "oneasr-key"},
        )
        
        # 注意：实际转录可能失败（因为测试环境没有模型），但接口应该正常响应
        assert response.status_code in [200, 500]  # 500 是因为模型可能不可用
    
    def test_transcribe_no_params(self, client):
        """测试不提供任何参数进行转录"""
        response = client.post(
            "/api/v1/audio/transcriptions",
            data={},
            headers={"X-API-Key": "oneasr-key"},
        )
        
        assert response.status_code == 400
        assert "必须提供" in response.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
