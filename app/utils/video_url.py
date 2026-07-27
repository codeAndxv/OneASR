"""平台视频 URL 解析与下载（抖音/TikTok/YouTube/B站）。

设计要点：
- yt-dlp 当 Python 库用（不是 subprocess 调 CLI），所有调用通过 asyncio.to_thread 投到线程池
- yt-dlp API 同步阻塞，FastAPI 在事件循环里跑，必须用 to_thread 桥接
- 进度通过 progress_hooks 回调写入数据库（上层服务注入）
- format=audio 走 bestaudio，format=video 走 bestvideo+bestaudio 合并 mp4
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yt_dlp

logger = logging.getLogger(__name__)

# 平台识别正则（顺序敏感：先匹配短链/分享链）
_PATTERNS: list[tuple[str, str]] = [
    ("douyin", r"(douyin\.com|iesdouyin\.com|v\.douyin\.com)"),
    ("tiktok", r"tiktok\.com|vm\.tiktok\.com"),
    ("bilibili", r"(bilibili\.com|b23\.tv)"),
    ("youtube", r"(youtube\.com|youtu\.be)"),
]

# 下载根目录（相对项目根，main.py 启动目录）
DOWNLOAD_DIR = Path("download")


def ensure_download_dir() -> Path:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return DOWNLOAD_DIR


def detect_platform(url: str) -> str:
    """根据 URL 推断平台，未知返回 'unknown'。"""
    for name, pat in _PATTERNS:
        if re.search(pat, url, re.I):
            return name
    return "unknown"


@dataclass
class VideoInfo:
    """extract_info 解析出的元数据。"""
    title: str
    duration_seconds: int | None
    uploader: str | None
    # yt-dlp 内部 extractor 名（如 'Douyin', 'Youtube', 'BiliBili'），便于调优
    extractor: str | None


def _build_ydl_opts(
    *,
    audio_only: bool,
    progress_hook: Callable[[dict], None] | None = None,
    max_filesize_bytes: int | None = None,
) -> dict:
    """组装 yt-dlp 选项 dict，避免拼命令行字符串。"""
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "no_color": True,
        # 文件名：download/{yt-dlp id}.{ext}
        "outtmpl": str(ensure_download_dir() / "%(id)s.%(ext)s"),
        # 选格式
        "format": "bestaudio/best" if audio_only else "bestvideo+bestaudio/best",
        # 视频合并为 mp4（需 ffmpeg）
        "merge_output_format": "mp4",
        # 限制并发下载分片，避免对源站压力
        "concurrent_fragment_downloads": 3,
        "retries": 5,
        "socket_timeout": 60,
    }
    if max_filesize_bytes is not None:
        opts["max_filesize"] = max_filesize_bytes
    if progress_hook is not None:
        opts["progress_hooks"] = [progress_hook]
    return opts


def _extract_info_sync(url: str, opts: dict) -> dict:
    """同步：仅解析元信息，不下载。"""
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.sanitize_info(ydl.extract_info(url, download=False))


def _download_sync(url: str, opts: dict) -> tuple[dict, str]:
    """同步：下载并返回 (info_dict, 实际落盘路径)。

    返回路径取 info['requested_downloads'][0]['filepath']，这是 yt-dlp
    下载/合并完成后写回的字段，名字固定、跨平台一致。
    """
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    downloads = info.get("requested_downloads") or []
    if not downloads:
        # 兜底：从 outtmpl 反查不到，仅记日志
        raise RuntimeError("yt-dlp 下载完成但未返回 requested_downloads")
    file_path = downloads[0].get("filepath")
    if not file_path:
        raise RuntimeError("yt-dlp requested_downloads 缺少 filepath 字段")
    return info, file_path


# ── 异步对外入口 ──────────────────────────────────────────────────

import asyncio  # noqa: E402 (放在文件末以保持同步工具区可读)


async def extract_info(url: str) -> VideoInfo:
    """异步解析元信息（不下载），用于提交任务时获取 title/duration/uploader。"""
    opts = _build_ydl_opts(audio_only=True)
    try:
        data = await asyncio.to_thread(_extract_info_sync, url, opts)
    except yt_dlp.utils.DownloadError as e:
        raise RuntimeError(f"URL 解析失败: {e}") from e
    return VideoInfo(
        title=data.get("title") or "",
        duration_seconds=data.get("duration"),
        uploader=data.get("uploader") or data.get("channel"),
        extractor=data.get("extractor_key") or data.get("extractor"),
    )


async def download_video(
    url: str,
    *,
    audio_only: bool,
    progress_hook: Callable[[dict], None] | None = None,
    max_filesize_bytes: int | None = None,
) -> tuple[VideoInfo, str, int]:
    """异步下载视频/音频，返回 (元信息, 本地路径, 文件大小字节)。

    progress_hook 是 yt-dlp 下载时回调，用于上层实时写 DB 进度：
      hook 内 dict 含 'downloaded_bytes'、'total_bytes'/'total_bytes_estimate'、'_percent_str'
    """
    opts = _build_ydl_opts(
        audio_only=audio_only,
        progress_hook=progress_hook,
        max_filesize_bytes=max_filesize_bytes,
    )
    try:
        info, file_path = await asyncio.to_thread(_download_sync, url, opts)
    except yt_dlp.utils.DownloadError as e:
        raise RuntimeError(f"视频下载失败: {e}") from e

    path = Path(file_path)
    video_info = VideoInfo(
        title=info.get("title") or "",
        duration_seconds=info.get("duration"),
        uploader=info.get("uploader") or info.get("channel"),
        extractor=info.get("extractor_key") or info.get("extractor"),
    )
    return video_info, str(path), path.stat().st_size if path.exists() else 0
