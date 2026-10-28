"""文件上传、资产管理与网络 URL 导入相关的 Pydantic 数据模式。"""

from typing import Optional
from pydantic import BaseModel, Field


class FileUploadResponse(BaseModel):
    """文件上传响应"""
    file_id: str = Field(..., description="文件UUID")
    filename: str = Field(..., description="原始文件名")
    file_size: int = Field(..., description="文件大小（字节）")
    file_md5: str = Field(..., description="文件 MD5")
    duplicate: bool = Field(default=False, description="是否为秒传（文件已存在）")
    message: str = Field(default="File uploaded successfully")


class LocalFileImportRequest(BaseModel):
    """本地文件直接导入请求（用于本地桌面端与本地路径导入，避免 HTTP 传输与磁盘二次复制）"""
    file_path: str = Field(..., description="本地文件绝对路径")


class FileInfo(BaseModel):
    """文件信息"""
    file_id: str = Field(..., description="文件UUID")
    filename: str = Field(..., description="原始文件名")
    file_size: int = Field(..., description="文件大小（字节）")
    file_md5: str = Field(..., description="文件 MD5")
    content_type: Optional[str] = Field(None, description="文件MIME类型")
    created_at: str = Field(..., description="上传时间")


class FileListResponse(BaseModel):
    """文件列表响应"""
    files: list[FileInfo] = Field(..., description="文件列表")
    total: int = Field(..., description="文件总数")


class FileDeleteResponse(BaseModel):
    """文件删除响应"""
    message: str = Field(..., description="删除结果")
    file_id: str = Field(..., description="删除的文件UUID")
