import tempfile
from pathlib import Path

import httpx

from app.core.config import settings

TEMP_DIR = Path(tempfile.gettempdir()) / "oneasr"


def ensure_temp_dir() -> Path:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    return TEMP_DIR


async def download_url(url: str) -> Path:
    """下载音视频 URL 到临时目录，返回文件路径。"""
    temp_dir = ensure_temp_dir()

    async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()

            # 从 Content-Disposition 或 URL 推断文件名
            filename = _extract_filename(resp, url)
            dest = temp_dir / filename

            size = 0
            max_bytes = settings.max_file_size_mb * 1024 * 1024
            with open(dest, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    size += len(chunk)
                    if size > max_bytes:
                        dest.unlink(missing_ok=True)
                        raise ValueError(f"文件超过大小限制 ({settings.max_file_size_mb}MB)")
                    f.write(chunk)

    return dest


def _extract_filename(resp: httpx.Response, url: str) -> str:
    cd = resp.headers.get("content-disposition", "")
    if "filename=" in cd:
        return cd.split("filename=")[-1].strip('" ')
    return Path(url.split("?")[0]).name or "download"
