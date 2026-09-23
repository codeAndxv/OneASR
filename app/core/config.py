from pathlib import Path

import yaml
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).parent.parent.parent


class EngineConfig:
    def __init__(self, name: str, config: dict, model_dir: Path | None = None):
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
        self.model_name = _get_val("model_name", "")
        self.model_path = _get_val("model_path", "")
        self.device = _get_val("device", "cpu")
        self.compute_type = _get_val("compute_type", "float32")
        self.max_duration = _get_val("max_duration")
        self.dtype = _get_val("dtype", "bfloat16")
        self.max_new_tokens = _get_val("max_new_tokens", 256)
        self.max_inference_batch_size = _get_val("max_inference_batch_size", 32)
        self.forced_aligner_name = _get_val("forced_aligner_name", _get_val("forced_aligner", ""))
        self.forced_aligner_path = _get_val("forced_aligner_path", "")
        self.forced_aligner = self.forced_aligner_name
        self.language = _get_val("language", "")

        # X-ASR 字段
        self.tokens_path = _get_val("tokens_path", _get_val("tokens", ""))
        self.encoder_path = _get_val("encoder_path", _get_val("encoder", ""))
        self.decoder_path = _get_val("decoder_path", _get_val("decoder", ""))
        self.joiner_path = _get_val("joiner_path", _get_val("joiner", ""))
        self.tokens = self.tokens_path
        self.encoder = self.encoder_path
        self.decoder = self.decoder_path
        self.joiner = self.joiner_path

        self.provider = _get_val("provider", "cpu")
        self.feature_dim = _get_val("feature_dim", 80)
        self.num_threads = _get_val("num_threads", 1)
        self.decoding_method = _get_val("decoding_method", "greedy_search")
        self.enable_endpoint_detection = _get_val("enable_endpoint_detection", False)

        # 功能支持
        self.functions: list[str] = _get_val("functions", [])

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


class AppConfig:
    def __init__(self, config_path: str | Path = None):
        config_path = config_path or PROJECT_ROOT / "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            self._data = yaml.safe_load(f) or {}

        # 兼容性保留（若配置文件中没有 model_dir 则为 None）
        model_dir_str = self._data.get("model_dir")
        if model_dir_str:
            self.model_dir = Path(model_dir_str)
            if not self.model_dir.is_absolute():
                self.model_dir = PROJECT_ROOT / self.model_dir
        else:
            self.model_dir = None

        # ASR-Toolkit 配置
        raw_toolkit = self._data.get("ASR-Toolkit", self._data.get("asr_toolkit", {}))
        self.asr_toolkit = ASRToolkitConfig(raw_toolkit)

        # ASR Providers
        self.providers: dict[str, EngineConfig] = {}
        for name, prov_conf in self._data.get("ASR-Providers", {}).items():
            self.providers[name] = EngineConfig(name, prov_conf, self.model_dir)

        # API Key 配置
        self.api_key = self._data.get("api_key", "")

    def get_provider_config(self, name: str) -> EngineConfig:
        if name not in self.providers:
            raise ValueError(f"未知 Provider: {name}，可用: {list(self.providers)}")
        return self.providers[name]


class Settings(BaseSettings):
    app_name: str = "OneASR"
    debug: bool = False
    max_file_size_mb: int = 500

    model_config = {"env_prefix": "ONEASR_"}


settings = Settings()
app_config = AppConfig()
