from pathlib import Path

import yaml
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).parent.parent.parent


class EngineConfig:
    def __init__(self, name: str, config: dict, model_dir: Path | None):
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
        self.device = _get_val("device", "cpu")
        self.compute_type = _get_val("compute_type", "float32")
        self.max_duration = _get_val("max_duration")
        self.dtype = _get_val("dtype", "bfloat16")
        self.max_new_tokens = _get_val("max_new_tokens", 256)
        self.max_inference_batch_size = _get_val("max_inference_batch_size", 32)
        self.forced_aligner = _get_val("forced_aligner", "")
        self.language = _get_val("language", "")
        # X-ASR 字段
        self.tokens = _get_val("tokens", "")
        self.encoder = _get_val("encoder", "")
        self.decoder = _get_val("decoder", "")
        self.joiner = _get_val("joiner", "")
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

    def resolve_model_path(self, identifier: str | None = None) -> str:
        """解析模型或权重文件的实际加载路径。

        逻辑：
        检查 model_dir + model_name 是否存在该目录/文件。
        如果存在，则返回 model_dir + model_name 路径；
        否则，返回 model_name。
        """
        ident = identifier if identifier is not None else self.model_name
        if not ident:
            return ""

        # 1. 检查 model_dir + ident 是否存在
        if self.model_dir:
            candidate = self.model_dir / ident
            if candidate.exists():
                return str(candidate)

        # 2. 若 ident 本身已是绝对路径或直接存在的相对路径
        path_obj = Path(ident)
        if path_obj.exists():
            return str(path_obj)

        # 3. 不存在本地目录时，返回原始名称（由引擎在线下载或作为云端标识）
        return ident


class AppConfig:
    def __init__(self, config_path: str | Path = None):
        config_path = config_path or PROJECT_ROOT / "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            self._data = yaml.safe_load(f)

        # 处理 model_dir
        model_dir_str = self._data.get("model_dir")
        if model_dir_str:
            self.model_dir = Path(model_dir_str)
            if not self.model_dir.is_absolute():
                self.model_dir = PROJECT_ROOT / self.model_dir
        else:
            self.model_dir = None

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
