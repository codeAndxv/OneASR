"""yt-dlp 配置与智能分流代理单元测试。"""

from app.core.config import YtDlpConfig, app_config
from app.utils.video_url import _build_ydl_opts, detect_platform


def test_ytdlp_config_loading():
    """测试 config.yaml 中 yt-dlp 配置正常加载。"""
    cfg = app_config.ytdlp
    assert isinstance(cfg, YtDlpConfig)
    assert cfg.enable is True
    assert cfg.download_dir == "download"
    assert cfg.socket_timeout == 60
    assert cfg.retries == 5
    assert cfg.concurrent_fragments == 3
    assert cfg.max_filesize_mb == 500


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
    opts = _build_ydl_opts(
        url="https://www.bilibili.com/video/BV123",
        audio_only=True
    )
    assert opts["format"] == "bestaudio/best"
    assert opts["merge_output_format"] == "mp4"
    assert opts["socket_timeout"] == 60
    assert opts["retries"] == 5
    assert opts["concurrent_fragment_downloads"] == 3
    assert opts["max_filesize"] == 500 * 1024 * 1024
