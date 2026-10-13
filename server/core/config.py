from pathlib import Path

import yaml
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).parent.parent.parent

WHISPER_SHORTHAND_MAP = {
    "tiny": "Systran/faster-whisper-tiny",
    "tiny.en": "Systran/faster-whisper-tiny.en",
    "base": "Systran/faster-whisper-base",
    "base.en": "Systran/faster-whisper-base.en",
    "small": "Systran/faster-whisper-small",
    "small.en": "Systran/faster-whisper-small.en",
    "medium": "Systran/faster-whisper-medium",
    "medium.en": "Systran/faster-whisper-medium.en",
    "large-v1": "Systran/faster-whisper-large-v1",
    "large-v2": "Systran/faster-whisper-large-v2",
    "large-v3": "Systran/faster-whisper-large-v3",
    "large": "Systran/faster-whisper-large-v3",
    "distil-large-v2": "Systran/faster-distil-whisper-large-v2",
    "distil-large-v3": "Systran/faster-distil-whisper-large-v3",
    "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
    "turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
}


def infer_whisper_repo_id(model_name: str | None) -> str:
    """根据 faster-whisper 的 model_name 推导对应的 HuggingFace / ModelScope 仓库 ID。"""
    name = (model_name or "medium").strip()
    if "/" in name:
        return name
    if name in WHISPER_SHORTHAND_MAP:
        return WHISPER_SHORTHAND_MAP[name]
    if name.startswith("faster-whisper-"):
        return f"Systran/{name}"
    return f"Systran/faster-whisper-{name}"


def parse_keep_alive_seconds(val, default: int = 600) -> int:
    """将 keep_alive 配置解析为秒数。

    支持：
    - 整数/浮点数：如 -1 (常驻), 0 (用完即焚), 600 (600秒)
    - 字符串时长：如 "10m" (600), "1h" (3600), "30s" (30), "-1", "0"
    """
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).strip().lower()
    if not s:
        return default
    if s in ("-1", "forever", "always", "permanent"):
        return -1
    if s in ("0", "0s", "immediate", "none"):
        return 0
    try:
        if s.endswith("ms"):
            return max(0, int(float(s[:-2]) / 1000))
        if s.endswith("s"):
            return int(float(s[:-1]))
        if s.endswith("m"):
            return int(float(s[:-1]) * 60)
        if s.endswith("h"):
            return int(float(s[:-1]) * 3600)
        return int(float(s))
    except ValueError:
        return default


class ModelManagerConfig:
    """全局模型生命周期管理配置（Ollama 风格 keep_alive + LRU 容量上限）。"""

    def __init__(self, data: dict | None = None):
        data = data or {}
        self.default_keep_alive: int = parse_keep_alive_seconds(
            data.get("default_keep_alive", data.get("keep_alive", 600)),
            default=600,
        )
        raw_max = data.get("max_loaded_models", 2)
        self.max_loaded_models: int = int(raw_max) if raw_max is not None else 2
        self.cleanup_interval: int = max(5, int(data.get("cleanup_interval", 30)))


class EngineConfig:
    def __init__(
        self,
        name: str,
        config: dict,
        model_dir: Path | None = None,
        default_keep_alive: int = 600,
    ):
        self.name = name
        self.raw_config = config
        self.model_dir = model_dir

        load_conf = config.get("load", {}) if isinstance(config.get("load"), dict) else {}
        props_conf = config.get("properties", {}) if isinstance(config.get("properties"), dict) else {}
        self.load = load_conf
        self.properties = props_conf

        def _get_val(key, default=None):
            if key in load_conf:
                return load_conf[key]
            if key in props_conf:
                return props_conf[key]
            return config.get(key, default)

        self.enable = bool(config.get("enable", config.get("enabled", True)))
        self.engine_name = config.get("engine", name)
        self.type = _get_val("type", "local")
        self.model_name = _get_val("model_name", "") or ""
        self.model_path = _get_val("model_path", "") or ""
        self.device = _get_val("device", "cpu")
        self.compute_type = _get_val("compute_type", "float32")
        self.max_duration = _get_val("max_duration")
        self.dtype = _get_val("dtype", "bfloat16")
        self.max_new_tokens = _get_val("max_new_tokens", 256)
        self.max_inference_batch_size = _get_val("max_inference_batch_size", 32)
        self.forced_aligner_name = _get_val("forced_aligner_name", _get_val("forced_aligner", "")) or ""
        self.forced_aligner_path = _get_val("forced_aligner_path", "") or ""
        self.forced_aligner = self.forced_aligner_name
        self.language = _get_val("language", "")

        # FunASR 字段
        self.vad_model = _get_val("vad_model", "") or ""
        self.vad_model_path = _get_val("vad_model_path", "") or ""
        self.punc_model = _get_val("punc_model", "") or ""
        self.punc_model_path = _get_val("punc_model_path", "") or ""

        # X-ASR 字段
        self.tokens_path = _get_val("tokens_path", _get_val("tokens", "")) or ""
        self.encoder_path = _get_val("encoder_path", _get_val("encoder", "")) or ""
        self.decoder_path = _get_val("decoder_path", _get_val("decoder", "")) or ""
        self.joiner_path = _get_val("joiner_path", _get_val("joiner", "")) or ""

        # 根据 model_name 自动推导 data/models/ 下的本地路径（当未显式指定 *_path 时）
        eng = (self.engine_name or name).lower()
        if self.type != "cloud":
            if eng in ("faster-whisper", "whisper"):
                if not self.model_path and self.model_name:
                    repo_id = infer_whisper_repo_id(self.model_name)
                    self.model_path = f"data/models/{repo_id.split('/')[-1]}"
            elif eng == "qwen":
                if not self.model_path and self.model_name:
                    self.model_path = f"data/models/{self.model_name.strip().split('/')[-1]}"
                if not self.forced_aligner_path and self.forced_aligner_name:
                    self.forced_aligner_path = (
                        f"data/models/{self.forced_aligner_name.strip().split('/')[-1]}"
                    )
            elif eng == "funasr":
                if not self.model_path and self.model_name:
                    raw_m = self.model_name.strip()
                    dir_name = (
                        "speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
                        if raw_m == "paraformer-zh"
                        else raw_m.split("/")[-1]
                    )
                    self.model_path = f"data/models/{dir_name}"
                if not self.vad_model_path and self.vad_model:
                    raw_v = self.vad_model.strip()
                    vad_dir = (
                        "speech_fsmn_vad_zh-cn-16k-common-pytorch"
                        if raw_v == "fsmn-vad"
                        else raw_v.split("/")[-1]
                    )
                    self.vad_model_path = f"data/models/{vad_dir}"
                if not self.punc_model_path and self.punc_model:
                    raw_p = self.punc_model.strip()
                    punc_dir = (
                        "punc_ct-transformer_cn-en-common-vocab471067-large"
                        if raw_p == "ct-punc"
                        else raw_p.split("/")[-1]
                    )
                    self.punc_model_path = f"data/models/{punc_dir}"
            elif eng == "xasr":
                has_explicit_xasr_files = any(
                    [self.tokens_path, self.encoder_path, self.decoder_path, self.joiner_path]
                )
                if not has_explicit_xasr_files and (self.model_path or self.model_name):
                    if self.model_path:
                        x_dir = self.model_path.rstrip("/")
                    else:
                        raw_x = self.model_name.strip()
                        if raw_x in (
                            "Gilgamesh-J/X-ASR-zh-en",
                            "GilgameshWind/X-ASR-zh-en",
                            "xasr-zh-en",
                            "chunk-160ms-model",
                        ):
                            x_dir = "data/models/chunk-160ms-model"
                        else:
                            x_dir = f"data/models/{raw_x.split('/')[-1]}"
                        self.model_path = x_dir
                    self.tokens_path = f"{x_dir}/tokens.txt"
                    self.encoder_path = f"{x_dir}/encoder-160ms.onnx"
                    self.decoder_path = f"{x_dir}/decoder-160ms.onnx"
                    self.joiner_path = f"{x_dir}/joiner-160ms.onnx"
            elif eng == "firered":
                if not self.model_path and self.model_name:
                    raw_f = self.model_name.strip()
                    f_dir = (
                        raw_f.split("/")[-1]
                        if "/" in raw_f
                        else "sherpa-onnx-fire-red-asr-large-zh_en-2025-02-16"
                    )
                    self.model_path = f"data/models/{f_dir}"

        self.tokens = self.tokens_path
        self.encoder = self.encoder_path
        self.decoder = self.decoder_path
        self.joiner = self.joiner_path

        self.provider = _get_val("provider", "cpu")
        self.feature_dim = _get_val("feature_dim", 80)
        self.num_threads = _get_val("num_threads", 1)
        self.decoding_method = _get_val("decoding_method", "greedy_search")
        self.enable_endpoint_detection = _get_val("enable_endpoint_detection", False)

        # 服务类别支持 (RealtimeASR / FileASR 等)
        self.categories: list[str] = _get_val("categories", _get_val("functions", []))
        self.functions: list[str] = self.categories  # 兼容旧代码引用

        # 生命周期策略：
        # - RealtimeASR 流式小模型默认 preload=True, keep_alive=-1 (常驻零延迟)
        # - FileASR 离线大模型默认 preload=False, keep_alive=default_keep_alive (按需加载 + 空闲释放)
        is_realtime = "RealtimeASR" in self.categories or self.engine_name == "xasr"
        is_cloud = self.type == "cloud" or self.engine_name in ("openai", "mimo")

        raw_preload = _get_val("preload", None)
        if raw_preload is None:
            self.preload: bool = bool(is_realtime)
        else:
            self.preload = bool(raw_preload)

        raw_keep_alive = _get_val("keep_alive", None)
        if raw_keep_alive is None:
            self.keep_alive: int = -1 if (is_realtime or is_cloud) else default_keep_alive
        else:
            self.keep_alive = parse_keep_alive_seconds(raw_keep_alive, default=default_keep_alive)

        # 高级特性支持 (asrAutoLanguageDetect, asrDiarization, asrWordTimestamp 等)
        raw_features = _get_val("features", None)
        if raw_features is None:
            self.features = ["asrAutoLanguageDetect"]
        elif isinstance(raw_features, str):
            self.features = [f.strip() for f in raw_features.split(",") if f.strip()]
        else:
            self.features = list(raw_features)

        # 支持的语言列表（逗号分隔字符串 → list）
        raw = _get_val("languages", "")
        if isinstance(raw, str):
            self.languages = [lang.strip() for lang in raw.split(",") if lang.strip()]
        else:
            self.languages = list(raw)

        # 云端引擎配置
        self.api_key = _get_val("api_key", "")
        self.base_url = _get_val("base_url", "")

        # 流式引擎配置
        self.sample_rate = _get_val("sample_rate", 16000)

    def resolve_path(self, path_str: str | None) -> Path | None:
        """将配置中的相对路径解析为相对于 PROJECT_ROOT 的完整路径。"""
        if not path_str or not str(path_str).strip():
            return None
        p = Path(path_str.strip())
        return p if p.is_absolute() else PROJECT_ROOT / p


class VADConfig:
    def __init__(self, data: dict | None = None):
        data = data or {}
        self.model: str = data.get("model", "silero_vad")
        self.threshold: float = float(data.get("threshold", 0.5))
        self.min_speech_duration_ms: int = int(data.get("min_speech_duration_ms", 250))
        self.min_silence_duration_ms: int = int(data.get("min_silence_duration_ms", 300))
        self.padding_ms: int = int(data.get("padding_ms", 100))


class ChunkingConfig:
    def __init__(self, data: dict | None = None):
        data = data or {}
        self.target_chunk_duration: float = float(data.get("target_chunk_duration", 6.0))
        self.max_chunk_duration: float = float(data.get("max_chunk_duration", 8.0))
        self.min_pause_duration: float = float(data.get("min_pause_duration", 0.4))
        self.min_sentence_duration: float = float(data.get("min_sentence_duration", 2.0))


class PostProcessConfig:
    def __init__(self, data: dict | None = None):
        data = data or {}
        self.remove_repeats: bool = bool(data.get("remove_repeats", True))
        self.normalize_text: bool = bool(data.get("normalize_text", True))


class ASRToolkitConfig:
    def __init__(self, data: dict | None = None):
        data = data or {}
        self.vad = VADConfig(data.get("vad", {}))
        self.chunking = ChunkingConfig(data.get("chunking", {}))
        self.post_process = PostProcessConfig(data.get("post_process", {}))


class YtDlpVideoConfig:
    def __init__(self, data: dict | None = None):
        data = data or {}
        self.max_resolution: str = str(data.get("max_resolution", "720p")).strip().lower()
        self.format: str = str(data.get("format", "mp4")).strip().lower()


class YtDlpAudioConfig:
    def __init__(self, data: dict | None = None):
        data = data or {}
        self.format: str = str(data.get("format", "best")).strip().lower()
        self.quality: str = str(data.get("quality", "best")).strip().lower()


class YtDlpMediaConfig:
    def __init__(self, data: dict | None = None):
        data = data or {}
        self.default_type: str = str(data.get("default_type", "audio")).strip().lower()
        self.video = YtDlpVideoConfig(data.get("video", {}))
        self.audio = YtDlpAudioConfig(data.get("audio", {}))


class YtDlpProxyConfig:
    def __init__(self, data: dict | None = None):
        data = data or {}
        self.url: str = data.get("url", "")
        raw_platforms = data.get("platforms", ["youtube", "tiktok"])
        if isinstance(raw_platforms, str):
            self.platforms = [p.strip().lower() for p in raw_platforms.split(",") if p.strip()]
        elif isinstance(raw_platforms, list):
            self.platforms = [str(p).strip().lower() for p in raw_platforms if p]
        else:
            self.platforms = []


class YtDlpConfig:
    def __init__(self, data: dict | None = None):
        data = data or {}
        self.enable: bool = bool(data.get("enable", True))
        self.download_dir: str = data.get("download_dir", "data/downloads")
        self.media = YtDlpMediaConfig(data.get("media", {}))
        self.proxy = YtDlpProxyConfig(data.get("proxy", {}))
        self.cookie_file: str = data.get("cookie_file", "")
        self.socket_timeout: int = int(data.get("socket_timeout", 60))
        self.retries: int = int(data.get("retries", 5))
        self.concurrent_fragments: int = int(data.get("concurrent_fragments", 3))
        raw_max_size = data.get("max_filesize_mb")
        self.max_filesize_mb: int | None = int(raw_max_size) if raw_max_size is not None else None
        self.ffmpeg_location: str | None = data.get("ffmpeg_location") or None

    def get_format_selector(self, media_type: str | None = None, resolution: str | None = None) -> str:
        """根据媒体类型 (audio/video) 与指定分辨率生成 yt-dlp format 表达式。"""
        import re

        effective_type = (media_type or self.media.default_type or "audio").lower().strip()
        if effective_type == "audio":
            return "bestaudio/best"

        eff_res = (resolution or self.media.video.max_resolution or "720p").lower().strip()
        if eff_res == "best" or not eff_res:
            return "bestvideo+bestaudio/best"

        match = re.search(r"\d+", eff_res)
        if match:
            h = match.group(0)
            return f"bestvideo[height<={h}]+bestaudio/best[height<={h}]/best"

        return "bestvideo+bestaudio/best"

    def get_proxy_for_url(self, url: str, platform: str = "") -> str | None:
        """根据 URL 及识别的平台，判断是否需要走代理。"""
        if not self.proxy.url or not self.proxy.url.strip():
            return None
        if not self.proxy.platforms or "all" in self.proxy.platforms:
            return self.proxy.url.strip()

        if not platform and url:
            from server.utils.video_url import detect_platform
            platform = detect_platform(url)

        if platform and platform.lower() in self.proxy.platforms:
            return self.proxy.url.strip()

        url_lower = url.lower()
        for p in self.proxy.platforms:
            if p in url_lower:
                return self.proxy.url.strip()

        return None


class AppConfig:
    def __init__(self, config_path: str | Path = None):
        config_path = config_path or PROJECT_ROOT / "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            self._data = yaml.safe_load(f) or {}

        model_dir_str = self._data.get("model_dir")
        if model_dir_str:
            self.model_dir = Path(model_dir_str)
            if not self.model_dir.is_absolute():
                self.model_dir = PROJECT_ROOT / self.model_dir
        else:
            self.model_dir = None

        # 模型生命周期管理配置
        raw_mm = (
            self._data.get("model_manager")
            or self._data.get("Model-Manager")
            or self._data.get("model-manager")
            or {}
        )
        self.model_manager = ModelManagerConfig(raw_mm)

        # ASR-Toolkit 配置
        raw_toolkit = self._data.get("ASR-Toolkit", self._data.get("asr_toolkit", {}))
        self.asr_toolkit = ASRToolkitConfig(raw_toolkit)

        # yt-dlp 配置（支持 yt-dlp, YT-DLP, ytdlp）
        raw_ytdlp = (
            self._data.get("yt-dlp")
            or self._data.get("YT-DLP")
            or self._data.get("ytdlp")
            or {}
        )
        self.ytdlp = YtDlpConfig(raw_ytdlp)

        # ASR Providers
        self.providers: dict[str, EngineConfig] = {}
        for name, prov_conf in self._data.get("ASR-Providers", {}).items():
            self.providers[name] = EngineConfig(
                name,
                prov_conf,
                self.model_dir,
                default_keep_alive=self.model_manager.default_keep_alive,
            )

        # API Key 配置
        self.api_key = self._data.get("api_key", "")

    def get_provider_config(self, name: str) -> EngineConfig:
        if name in self.providers:
            return self.providers[name]

        raise ValueError(f"未知 Provider: {name}，可用: {list(self.providers)}")


class Settings(BaseSettings):
    app_name: str = "OneASR"
    app_version: str = "0.1.0"
    api_version: str = "0.1.0"
    debug: bool = False
    max_file_size_mb: int = 500

    model_config = {"env_prefix": "ONEASR_"}


settings = Settings()
app_config = AppConfig()
API_VERSION = settings.api_version
