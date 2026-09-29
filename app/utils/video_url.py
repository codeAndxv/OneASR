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

# 下载根目录默认路径（具体以 config.yaml 为准）
DOWNLOAD_DIR = Path("download")


def ensure_download_dir() -> Path:
    from app.core.config import PROJECT_ROOT, app_config
    dir_str = app_config.ytdlp.download_dir or "download"
    p = Path(dir_str)
    target = p if p.is_absolute() else PROJECT_ROOT / p
    target.mkdir(parents=True, exist_ok=True)
    return target


def is_direct_media_url(url: str) -> bool:
    """判断是否为直接的音视频文件 URL。"""
    clean_url = url.split("?")[0].split("#")[0].lower()
    return any(clean_url.endswith(ext) for ext in [
        ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma",
        ".mp4", ".mov", ".mkv", ".webm", ".avi", ".flv", ".ts"
    ])


def detect_platform(url: str) -> str:
    """根据 URL 推断平台，直链返回 'direct'，未知返回 'unknown'。"""
    for name, pat in _PATTERNS:
        if re.search(pat, url, re.I):
            return name
    if is_direct_media_url(url):
        return "direct"
    return "unknown"


@dataclass
class VideoInfo:
    """extract_info 解析出的元数据。"""
    title: str
    duration_seconds: float | None
    uploader: str | None
    # yt-dlp 内部 extractor 名（如 'Douyin', 'Youtube', 'BiliBili'），便于调优
    extractor: str | None


def _build_ydl_opts(
    *,
    url: str = "",
    audio_only: bool,
    progress_hook: Callable[[dict], None] | None = None,
    max_filesize_bytes: int | None = None,
) -> dict:
    """组装 yt-dlp 选项 dict，避免拼命令行字符串。"""
    from app.core.config import PROJECT_ROOT, app_config

    cfg = app_config.ytdlp
    platform = detect_platform(url) if url else ""

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
        "concurrent_fragment_downloads": cfg.concurrent_fragments,
        "retries": cfg.retries,
        "socket_timeout": cfg.socket_timeout,
    }

    # 智能分流代理（如仅 YouTube / TikTok 走代理，B站/抖音 直连）
    if url:
        proxy_url = cfg.get_proxy_for_url(url, platform)
        if proxy_url:
            opts["proxy"] = proxy_url

    # Cookie 凭证支持
    if cfg.cookie_file and cfg.cookie_file.strip():
        cp = Path(cfg.cookie_file.strip())
        cookie_path = cp if cp.is_absolute() else PROJECT_ROOT / cp
        if cookie_path.exists():
            opts["cookiefile"] = str(cookie_path)
        else:
            logger.warning("配置的 cookie_file 不存在: %s", cookie_path)

    # 自定义 FFmpeg 路径
    if cfg.ffmpeg_location and cfg.ffmpeg_location.strip():
        opts["ffmpeg_location"] = cfg.ffmpeg_location.strip()

    # 最大文件大小限制
    if max_filesize_bytes is not None:
        opts["max_filesize"] = max_filesize_bytes
    elif cfg.max_filesize_mb is not None:
        opts["max_filesize"] = cfg.max_filesize_mb * 1024 * 1024

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
    opts = _build_ydl_opts(url=url, audio_only=True)
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
        url=url,
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


def _try_get_duration(file_path: str) -> float | None:
    """尝试获取音频/视频文件时长（秒）。"""
    try:
        import torchaudio
        info = torchaudio.info(file_path)
        if info.sample_rate and info.num_frames:
            return round(info.num_frames / info.sample_rate, 3)
    except Exception:
        pass
    return None


async def download_direct_media(
    url: str,
    *,
    audio_only: bool = True,
    progress_hook: Callable[[dict], None] | None = None,
    max_filesize_bytes: int | None = None,
) -> tuple[VideoInfo, str, int]:
    """下载音视频直链，返回 (VideoInfo, 本地文件路径, 文件大小字节)。"""
    import uuid
    import httpx
    from app.core.config import app_config

    download_dir = ensure_download_dir()
    proxy = app_config.ytdlp.get_proxy_for_url(url, "direct")
    effective_max_bytes = max_filesize_bytes
    if effective_max_bytes is None and app_config.ytdlp.max_filesize_mb:
        effective_max_bytes = app_config.ytdlp.max_filesize_mb * 1024 * 1024

    async with httpx.AsyncClient(timeout=app_config.ytdlp.socket_timeout, proxy=proxy, follow_redirects=True) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()

            # 解析文件名
            cd = resp.headers.get("content-disposition", "")
            filename = ""
            if "filename=" in cd:
                filename = cd.split("filename=")[-1].strip('"\' ')
            if not filename:
                raw_name = Path(url.split("?")[0].split("#")[0]).name
                filename = raw_name or f"{uuid.uuid4().hex[:12]}.mp3"

            file_path = download_dir / f"{uuid.uuid4().hex[:8]}_{filename}"
            total_bytes = int(resp.headers.get("content-length") or 0)

            downloaded = 0
            with open(file_path, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    downloaded += len(chunk)
                    if effective_max_bytes and downloaded > effective_max_bytes:
                        file_path.unlink(missing_ok=True)
                        raise ValueError(f"文件大小超出限制: {effective_max_bytes} bytes")
                    f.write(chunk)
                    if progress_hook:
                        progress_hook({
                            "status": "downloading",
                            "downloaded_bytes": downloaded,
                            "total_bytes": total_bytes or None,
                        })

            if progress_hook:
                progress_hook({"status": "finished"})

    duration = _try_get_duration(str(file_path))
    video_info = VideoInfo(
        title=Path(filename).stem,
        duration_seconds=duration,
        uploader=None,
        extractor="DirectURL",
    )
    return video_info, str(file_path), downloaded
