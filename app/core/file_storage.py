"""
文件存储管理模块 - 处理大文件上传和管理
"""

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.core.config import app_config

logger = logging.getLogger(__name__)

# 文件存储目录
UPLOAD_DIR = Path(app_config.upload_dir) if hasattr(app_config, 'upload_dir') else Path("./uploads")
METADATA_FILE = UPLOAD_DIR / "metadata.json"


class FileMetadata:
    """文件元数据"""
    def __init__(self, file_id: str, filename: str, file_path: str, file_size: int, 
                 content_type: str, created_at: str):
        self.file_id = file_id
        self.filename = filename
        self.file_path = file_path
        self.file_size = file_size
        self.content_type = content_type
        self.created_at = created_at

    def to_dict(self):
        return {
            "file_id": self.file_id,
            "filename": self.filename,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "content_type": self.content_type,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            file_id=data["file_id"],
            filename=data["filename"],
            file_path=data["file_path"],
            file_size=data["file_size"],
            content_type=data["content_type"],
            created_at=data["created_at"],
        )


class FileStorage:
    """文件存储管理器"""
    
    def __init__(self):
        self.upload_dir = UPLOAD_DIR
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self._metadata = self._load_metadata()
    
    def _load_metadata(self) -> dict[str, FileMetadata]:
        """加载文件元数据"""
        if METADATA_FILE.exists():
            try:
                with open(METADATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {k: FileMetadata.from_dict(v) for k, v in data.items()}
            except Exception as e:
                logger.error("Failed to load metadata: %s", e)
        return {}
    
    def _save_metadata(self):
        """保存文件元数据"""
        try:
            data = {k: v.to_dict() for k, v in self._metadata.items()}
            with open(METADATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Failed to save metadata: %s", e)
    
    async def save_file(self, filename: str, file_content: bytes, content_type: str) -> str:
        """
        保存上传的文件
        
        Args:
            filename: 原始文件名
            file_content: 文件内容
            content_type: 文件MIME类型
            
        Returns:
            文件UUID
        """
        file_id = str(uuid.uuid4())
        file_ext = Path(filename).suffix
        saved_filename = f"{file_id}{file_ext}"
        file_path = self.upload_dir / saved_filename
        
        # 保存文件
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        # 保存元数据
        metadata = FileMetadata(
            file_id=file_id,
            filename=filename,
            file_path=str(file_path),
            file_size=len(file_content),
            content_type=content_type,
            created_at=datetime.now().isoformat(),
        )
        self._metadata[file_id] = metadata
        self._save_metadata()
        
        logger.info("File saved: %s (ID: %s, Size: %d bytes)", filename, file_id, len(file_content))
        return file_id
    
    def get_file(self, file_id: str) -> Optional[FileMetadata]:
        """获取文件元数据"""
        return self._metadata.get(file_id)
    
    def get_file_path(self, file_id: str) -> Optional[Path]:
        """获取文件路径"""
        metadata = self._metadata.get(file_id)
        if metadata:
            path = Path(metadata.file_path)
            if path.exists():
                return path
        return None
    
    def list_files(self) -> list[FileMetadata]:
        """列出所有已上传的文件"""
        return list(self._metadata.values())
    
    def delete_file(self, file_id: str) -> bool:
        """
        删除文件
        
        Args:
            file_id: 文件UUID
            
        Returns:
            是否删除成功
        """
        metadata = self._metadata.get(file_id)
        if not metadata:
            return False
        
        # 删除物理文件
        file_path = Path(metadata.file_path)
        if file_path.exists():
            file_path.unlink()
        
        # 删除元数据
        del self._metadata[file_id]
        self._save_metadata()
        
        logger.info("File deleted: %s (ID: %s)", metadata.filename, file_id)
        return True


# 全局文件存储实例
file_storage = FileStorage()
