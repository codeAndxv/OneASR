"""yt-dlp 配置与智能分流代理单元测试。"""

from server.core.config import YtDlpConfig, app_config
from server.utils.video_url import _build_ydl_opts, detect_platform


def test_ytdlp_config_loading():
    """测试 config.yaml 中 yt-dlp 配置正常加载。"""
    cfg = app_config.ytdlp
    assert isinstance(cfg, YtDlpConfig)
    assert cfg.enable is True
    assert cfg.download_dir == "data/downloads"
    assert cfg.media.default_type == "audio"
    assert cfg.media.video.max_resolution == "720p"
    assert cfg.media.video.format == "mp4"
    assert cfg.media.audio.format == "best"
    assert cfg.socket_timeout == 60
    assert cfg.retries == 5
    assert cfg.concurrent_fragments == 3
    assert cfg.max_filesize_mb == 500


def test_format_selector():
    """测试不同媒体类型与分辨率的 yt-dlp 表达式生成。"""
    cfg = app_config.ytdlp

    # 1. 纯音频
    assert cfg.get_format_selector("audio") == "bestaudio/best"

    # 2. 视频 720p
    assert cfg.get_format_selector("video", "720p") == "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
    assert cfg.get_format_selector("video", "720") == "bestvideo[height<=720]+bestaudio/best[height<=720]/best"

    # 3. 视频 1080p
    assert cfg.get_format_selector("video", "1080p") == "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"

    # 4. 视频 480p / 360p
    assert cfg.get_format_selector("video", "480p") == "bestvideo[height<=480]+bestaudio/best[height<=480]/best"
    assert cfg.get_format_selector("video", "360p") == "bestvideo[height<=360]+bestaudio/best[height<=360]/best"

    # 5. 视频 best (无上限)
    assert cfg.get_format_selector("video", "best") == "bestvideo+bestaudio/best"


def test_proxy_routing_whitelist():
    """测试白名单代理分流逻辑。"""
    raw = {
        "enable": True,
        "proxy": {
            "url": "http://127.0.0.1:7890",
            "platforms": ["youtube", "tiktok"]
        }
    }
    cfg = YtDlpConfig(raw)

    # 1. YouTube / TikTok 走代理
    assert cfg.get_proxy_for_url("https://www.youtube.com/watch?v=123", "youtube") == "http://127.0.0.1:7890"
    assert cfg.get_proxy_for_url("https://vm.tiktok.com/ZM8abc/", "tiktok") == "http://127.0.0.1:7890"
    assert cfg.get_proxy_for_url("https://youtu.be/xyz") == "http://127.0.0.1:7890"

    # 2. B站 / 抖音 直连不走代理
    assert cfg.get_proxy_for_url("https://www.bilibili.com/video/BV1xx411c7mD", "bilibili") is None
    assert cfg.get_proxy_for_url("https://v.douyin.com/abc/", "douyin") is None
    assert cfg.get_proxy_for_url("https://example.com/audio.mp3", "direct") is None


def test_proxy_routing_all():
    """测试全量代理逻辑。"""
    raw = {
        "enable": True,
        "proxy": {
            "url": "http://127.0.0.1:7890",
            "platforms": ["all"]
        }
    }
    cfg = YtDlpConfig(raw)
    assert cfg.get_proxy_for_url("https://www.bilibili.com/video/BV1", "bilibili") == "http://127.0.0.1:7890"
    assert cfg.get_proxy_for_url("https://www.youtube.com/watch?v=1", "youtube") == "http://127.0.0.1:7890"


def test_build_ydl_opts():
    """测试 _build_ydl_opts 正确装配配置参数。"""
    # 纯音频下载
    audio_opts = _build_ydl_opts(
        url="https://www.bilibili.com/video/BV123",
        audio_only=True
    )
    assert audio_opts["format"] == "bestaudio/best"
    assert "merge_output_format" not in audio_opts
    assert audio_opts["socket_timeout"] == 60
    assert audio_opts["retries"] == 5
    assert audio_opts["concurrent_fragment_downloads"] == 3
    assert audio_opts["max_filesize"] == 500 * 1024 * 1024

    # 视频 1080p 下载
    video_opts = _build_ydl_opts(
        url="https://www.youtube.com/watch?v=123",
        audio_only=False,
        resolution="1080p"
    )
    assert video_opts["format"] == "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
    assert video_opts["merge_output_format"] == "mp4"
