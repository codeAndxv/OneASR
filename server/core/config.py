"""OneASR core configuration and dynamic engine settings.

Operates with zero required configuration files (Ollama style).
Combines environment variables, dynamic filesystem scanning (~/.oneasr/models),
and an atomic settings.json store, while optionally supporting legacy YAML
overrides when explicitly supplied.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings

from server.core.manifest import BUILTIN_MODELS, get_manifest
from server.core.paths import (
    PROJECT_ROOT,
    ensure_directories,
    get_models_dir,
    get_settings_path,
)
from server.core.scanner import scan_all_models

logger = logging.getLogger(__name__)

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
    """Infer the HuggingFace / ModelScope repository ID from a model shorthand name."""
    name = (model_name or "medium").strip()
    if "/" in name:
        return name
    if name in WHISPER_SHORTHAND_MAP:
        return WHISPER_SHORTHAND_MAP[name]
    if name.startswith("faster-whisper-"):
        return f"Systran/{name}"
    return f"Systran/faster-whisper-{name}"


def parse_keep_alive_seconds(val: Any, default: int = 600) -> int:
    """Parse keep_alive setting into integer seconds.

    Supports:
    - Numeric values: -1 (resident), 0 (immediate release), 600 (seconds)
    - Duration strings: '10m', '1h', '30s', 'forever', 'always', 'immediate'
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
    """Global model lifecycle configuration (Ollama-style keep_alive and LRU eviction)."""

    def __init__(self, data: dict | None = None):
        data = data or {}
        env_keep_alive = os.getenv("ONEASR_KEEP_ALIVE")
        raw_val = env_keep_alive if env_keep_alive is not None else data.get("default_keep_alive", data.get("keep_alive", 600))
        self.default_keep_alive: int = parse_keep_alive_seconds(raw_val, default=600)
        raw_max = os.getenv("ONEASR_MAX_LOADED_MODELS") or data.get("max_loaded_models", 2)
        self.max_loaded_models: int = int(raw_max) if raw_max is not None else 2
        self.cleanup_interval: int = max(5, int(data.get("cleanup_interval", 30)))


DRIVER_ALIAS_MAP: dict[str, str] = {
    "faster-whisper": "whisper",
    "qwen-asr": "qwen",
    "openai-compatible": "openai",
    "firered-asr": "firered",
    "fireredasr": "firered",
}


class EngineConfig:
    """Configuration for an individual local or cloud ASR engine."""

    def __init__(
        self,
        name: str,
        config: dict,
        model_dir: Path | None = None,
        default_keep_alive: int = 600,
        is_cloud: bool = False,
    ):
        self.name = name
        self.raw_config = config
        self.model_dir = model_dir
        self.is_cloud = is_cloud

        model_conf = config.get("model", {}) if isinstance(config.get("model"), dict) else {}
        runtime_conf = config.get("runtime", {}) if isinstance(config.get("runtime"), dict) else {}
        caps_conf = config.get("capabilities", {}) if isinstance(config.get("capabilities"), dict) else {}
        load_conf = config.get("load", {}) if isinstance(config.get("load"), dict) else {}
        props_conf = config.get("properties", {}) if isinstance(config.get("properties"), dict) else {}

        self.load = load_conf or runtime_conf
        self.properties = props_conf or caps_conf

        def _get_val(key: str, default: Any = None) -> Any:
            for d in (runtime_conf, model_conf, caps_conf, load_conf, props_conf):
                if key in d:
                    return d[key]
            return config.get(key, default)

        self.enable = bool(config.get("enable", config.get("enabled", True)))
        raw_driver = config.get("driver") or config.get("engine") or name
        self.driver = raw_driver
        self.engine_name = DRIVER_ALIAS_MAP.get(raw_driver, raw_driver)
        self.type = "cloud" if is_cloud else _get_val("type", "local")
        if self.type == "cloud":
            self.is_cloud = True

        self.model_name = _get_val("repo", _get_val("model_name", "")) or ""
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

        # FunASR fields
        self.vad_model = _get_val("vad_repo", _get_val("vad_model", "")) or ""
        self.vad_model_path = _get_val("vad_model_path", "") or ""
        self.punc_model = _get_val("punc_repo", _get_val("punc_model", "")) or ""
        self.punc_model_path = _get_val("punc_model_path", "") or ""

        # X-ASR streaming fields
        self.tokens_path = _get_val("tokens_path", _get_val("tokens", "")) or ""
        self.encoder_path = _get_val("encoder_path", _get_val("encoder", "")) or ""
        self.decoder_path = _get_val("decoder_path", _get_val("decoder", "")) or ""
        self.joiner_path = _get_val("joiner_path", _get_val("joiner", "")) or ""

        # Path resolution for local models
        eng = (self.engine_name or name).lower()
        if not self.is_cloud:
            if eng in ("whisper", "faster-whisper"):
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

        # Service categories and capabilities
        self.categories: list[str] = _get_val("categories", _get_val("functions", []))
        self.functions: list[str] = self.categories

        is_realtime = "RealtimeASR" in self.categories or self.engine_name == "xasr"
        is_cloud = self.is_cloud or self.type == "cloud" or self.engine_name == "openai"

        raw_preload = _get_val("preload", None)
        self.preload = bool(is_realtime) if raw_preload is None else bool(raw_preload)

        raw_keep_alive = _get_val("keep_alive", None)
        if raw_keep_alive is None:
            self.keep_alive: int = -1 if (is_realtime or is_cloud) else default_keep_alive
        else:
            self.keep_alive = parse_keep_alive_seconds(raw_keep_alive, default=default_keep_alive)

        raw_features = _get_val("features", None)
        if raw_features is None:
            self.features = ["asrAutoLanguageDetect"]
        elif isinstance(raw_features, str):
            self.features = [f.strip() for f in raw_features.split(",") if f.strip()]
        else:
            self.features = list(raw_features)

        raw_langs = _get_val("languages", "")
        if isinstance(raw_langs, str):
            self.languages = [lang.strip() for lang in raw_langs.split(",") if lang.strip()]
        else:
            self.languages = list(raw_langs)

        self.api_key = _get_val("api_key", "")
        self.base_url = _get_val("base_url", "")
        self.sample_rate = _get_val("sample_rate", 16000)

    def resolve_path(self, path_str: str | None) -> Path | None:
        """Resolve a relative path against PROJECT_ROOT or return an absolute path as-is."""
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
        raw_max_size = data.get("max_filesize_mb", 500)
        self.max_filesize_mb: int | None = int(raw_max_size) if raw_max_size is not None else 500
        self.ffmpeg_location: str | None = data.get("ffmpeg_location") or None

    def get_format_selector(self, media_type: str | None = None, resolution: str | None = None) -> str:
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
    """Central application configuration with Ollama-style zero-config runtime."""

    def __init__(self, config_path: str | Path | None = None):
        ensure_directories()
        self.model_dir = get_models_dir()

        self._data: dict[str, Any] = {}
        self.providers: dict[str, EngineConfig] = {}
        self.local_models: dict[str, EngineConfig] = {}
        self.cloud_providers: dict[str, dict] = {}

        # 1. Check if an explicit config file was requested, or fallback to config.yaml
        explicit_file = Path(config_path) if config_path else None
        if not explicit_file:
            candidates = [
                Path("config.yaml"),
                Path(__file__).parent.parent.parent / "config.yaml",
            ]
            for c in candidates:
                if c.is_file():
                    explicit_file = c
                    break

        if explicit_file and explicit_file.is_file():
            try:
                with open(explicit_file, "r", encoding="utf-8") as f:
                    self._data = yaml.safe_load(f) or {}
                logger.info("Loaded configuration from file: %s", explicit_file)
            except Exception as e:
                logger.warning("Failed to parse config file %s: %s", explicit_file, e)

        # 2. Check settings.json in ~/.oneasr
        settings_file = get_settings_path()
        user_settings: dict[str, Any] = {}
        if settings_file.is_file():
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    user_settings = json.load(f) or {}
            except Exception as e:
                logger.warning("Failed to parse user settings file %s: %s", settings_file, e)

        # 3. Model manager lifecycle config
        raw_mm = self._data.get("model_manager") or {}
        if not raw_mm and "keep_alive" in user_settings:
            raw_mm["default_keep_alive"] = user_settings["keep_alive"]
        self.model_manager = ModelManagerConfig(raw_mm)

        # 4. ASR Toolkit and yt-dlp config
        self.asr_toolkit = ASRToolkitConfig(self._data.get("ASR-Toolkit", {}))
        self.ytdlp = YtDlpConfig(self._data.get("yt-dlp", {}))

        # 5. API Key resolution: Environment > explicit config > settings.json > default standard key
        self.api_key = (
            os.getenv("ONEASR_API_KEY")
            or self._data.get("api_key")
            or user_settings.get("api_key")
            or "sk-oneasr-v1-p_L3kXm9QZ8sT2vA4wE7rY1u"
        )

        # 6. Parse legacy local-models and cloud-providers if present in _data
        self._parse_yaml_providers()

        # 7. Merge dynamic models from built-in manifest and disk scan
        self.refresh_models()

    def _parse_yaml_providers(self) -> None:
        """Parse explicit local-models and cloud-providers from YAML if present."""
        raw_local = (
            self._data.get("local-models")
            or self._data.get("Local-Models")
            or self._data.get("local_models")
            or {}
        )
        if isinstance(raw_local, dict):
            for name, model_conf in raw_local.items():
                if not isinstance(model_conf, dict):
                    continue
                cfg = EngineConfig(
                    name,
                    model_conf,
                    self.model_dir,
                    default_keep_alive=self.model_manager.default_keep_alive,
                    is_cloud=False,
                )
                self.local_models[name] = cfg
                self.providers[name] = cfg

        raw_cloud = (
            self._data.get("cloud-providers")
            or self._data.get("Cloud-Providers")
            or self._data.get("cloud_providers")
            or {}
        )
        if isinstance(raw_cloud, dict):
            for prov_name, prov_conf in raw_cloud.items():
                if not isinstance(prov_conf, dict):
                    continue
                self.cloud_providers[prov_name] = prov_conf
                if not prov_conf.get("enable", True):
                    continue

                driver = prov_conf.get("driver") or prov_conf.get("engine") or "openai"
                conn = prov_conf.get("connection", {}) if isinstance(prov_conf.get("connection"), dict) else prov_conf
                api_key = conn.get("api_key") or prov_conf.get("api_key", "")
                base_url = conn.get("base_url") or prov_conf.get("base_url", "")
                timeout = conn.get("timeout") or prov_conf.get("timeout", 30)
                proxy = conn.get("proxy") or prov_conf.get("proxy", "")

                for m in prov_conf.get("models", []):
                    if isinstance(m, str):
                        m_id = m
                        m_remote = m
                        m_cats = ["FileASR"]
                        m_langs = []
                    elif isinstance(m, dict):
                        m_id = m.get("id") or m.get("name")
                        m_remote = m.get("remote_name") or m.get("remote_model") or m_id
                        m_cats = m.get("categories", ["FileASR"])
                        m_langs = m.get("languages", [])
                    else:
                        continue

                    if not m_id:
                        continue

                    cfg = EngineConfig(
                        m_id,
                        {
                            "enable": True,
                            "driver": driver,
                            "type": "cloud",
                            "provider": prov_name,
                            "api_key": api_key,
                            "base_url": base_url,
                            "timeout": timeout,
                            "proxy": proxy,
                            "model_name": m_remote,
                            "remote_model": m_remote,
                            "categories": m_cats,
                            "languages": m_langs,
                            "keep_alive": -1,
                            "preload": False,
                        },
                        self.model_dir,
                        default_keep_alive=-1,
                        is_cloud=True,
                    )
                    self.providers[m_id] = cfg

    def refresh_models(self) -> None:
        """Scan disk and built-in manifest to dynamically update providers without restart."""
        scanned = scan_all_models()
        for model_id, res in scanned.items():
            # If already explicitly defined in YAML, do not overwrite
            if model_id in self.local_models and self._data:
                continue

            is_ready = res.status == "ready"
            model_path_str = str(res.model_path) if res.model_path else ""

            cfg_data = {
                "enable": is_ready,
                "driver": res.driver,
                "type": "local",
                "model_name": res.repo,
                "model_path": model_path_str,
                "categories": res.categories,
                "languages": res.languages,
                "features": res.features,
                "preload": res.preload,
                "keep_alive": res.keep_alive,
                **res.extra,
            }

            # Map X-ASR specific sub-paths if path is resolved
            if res.driver == "xasr" and res.model_path:
                cfg_data["tokens_path"] = str(res.model_path / "tokens.txt")
                cfg_data["encoder_path"] = str(res.model_path / "encoder-160ms.onnx")
                cfg_data["decoder_path"] = str(res.model_path / "decoder-160ms.onnx")
                cfg_data["joiner_path"] = str(res.model_path / "joiner-160ms.onnx")

            cfg = EngineConfig(
                model_id,
                cfg_data,
                self.model_dir,
                default_keep_alive=self.model_manager.default_keep_alive,
                is_cloud=False,
            )
            if not self._data:
                self.local_models[model_id] = cfg
            self.providers[model_id] = cfg

    def get_provider_config(self, name: str) -> EngineConfig:
        """Find engine config by direct ID, alias, or driver matching."""
        if name in self.providers:
            return self.providers[name]

        # Check aliases from manifest
        manifest = get_manifest(name)
        if manifest and manifest.id in self.providers:
            return self.providers[manifest.id]

        # Support shorthand lookup (e.g. 'whisper-turbo' matching 'groq/whisper-turbo')
        for prov_id, cfg in self.providers.items():
            if prov_id.split("/")[-1] == name:
                return cfg

        # Match by driver or engine_name fallback (e.g. 'faster-whisper', 'funasr')
        for cfg in self.providers.values():
            if cfg.driver == name or cfg.engine_name == name:
                return cfg

        raise ValueError(f"Unknown Provider / Model: {name}, available: {list(self.providers)}")

    def save_settings(self, updates: dict[str, Any]) -> None:
        """Atomically persist user settings into ~/.oneasr/settings.json."""
        settings_file = get_settings_path()
        current: dict[str, Any] = {}
        if settings_file.is_file():
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    current = json.load(f) or {}
            except Exception:
                pass

        current.update(updates)
        dir_name = settings_file.parent
        dir_name.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tmp:
            json.dump(current, tmp, indent=2, ensure_ascii=False)
            tmp_path = Path(tmp.name)
        tmp_path.replace(settings_file)


class Settings(BaseSettings):
    """Global system environment and server metadata."""

    app_name: str = "OneASR"
    app_version: str = "0.1.0"
    api_version: str = "0.1.0"
    debug: bool = False
    max_file_size_mb: int = 500

    model_config = {"env_prefix": "ONEASR_"}


settings = Settings()
app_config = AppConfig()
API_VERSION = settings.api_version
