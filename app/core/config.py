from pathlib import Path

import yaml
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).parent.parent.parent


class EngineConfig:
    def __init__(self, name: str, config: dict, model_dir: Path | None):
        self.name = name
        self.raw_config = config
        self.model_dir = model_dir
        self.enable = bool(config.get("enable", config.get("enabled", True)))
        self.engine_name = config.get("engine", name)
        self.type = config.get("type", "local")
        self.model_name = config.get("model_name", "")
        self.model_path = config.get("model_path", "")  # 显式指定的本地模型路径
        self.device = config.get("device", "cpu")
        self.compute_type = config.get("compute_type", "float32")
        self.max_duration = config.get("max_duration")
        self.dtype = config.get("dtype", "bfloat16")
        self.max_new_tokens = config.get("max_new_tokens", 256)
        self.max_inference_batch_size = config.get("max_inference_batch_size", 32)
        self.forced_aligner = config.get("forced_aligner", "")
        self.forced_aligner_path = config.get("forced_aligner_path", "")
        self.language = config.get("language", "")
        # X-ASR 字段
        self.tokens = config.get("tokens", "")
        self.encoder = config.get("encoder", "")
        self.decoder = config.get("decoder", "")
        self.joiner = config.get("joiner", "")
        self.provider = config.get("provider", "cpu")
        self.num_threads = config.get("num_threads", 1)
        self.decoding_method = config.get("decoding_method", "greedy_search")
        self.enable_endpoint_detection = config.get("enable_endpoint_detection", False)
        # 功能支持
        self.functions: list[str] = config.get("functions", [])
        # 支持的语言列表（逗号分隔字符串 → list）
        raw = config.get("languages", "")
        if isinstance(raw, str):
            self.languages = [lang.strip() for lang in raw.split(",") if lang.strip()]
        else:
            self.languages = list(raw)
        # 云端引擎配置
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "")
        # 流式引擎配置
        self.sample_rate = config.get("sample_rate", 16000)

    def resolve_model_path(self, identifier: str | None = None) -> str:
        """解析模型或权重文件的实际加载路径。

        规则：
        1. 若未传入特定的 identifier，且配置中显式指定了 self.model_path：
           - 首先检查 self.model_path（绝对路径、相对 PROJECT_ROOT、或相对 model_dir）
           - 若本地存在，直接返回该绝对路径；若指定了路径但尚未下载，返回解析后的路径
        2. 若未指定 self.model_path 或指定了具体 identifier：
           - 使用 identifier（默认使用 self.model_name）
           - 优先探测本地是否存在（绝对路径、相对 PROJECT_ROOT、model_dir/identifier、model_dir/pure_name）
           - 若本地存在则返回本地绝对路径
           - 若本地不存在则返回原始名称（由引擎在线下载）
        """
        # 1. 未传入特定 identifier 且配置了显式 model_path
        if identifier is None and self.model_path:
            p_obj = Path(self.model_path)
            if p_obj.is_absolute() and p_obj.exists():
                return str(p_obj)
            proj_rel = PROJECT_ROOT / p_obj
            if proj_rel.exists():
                return str(proj_rel)
            if self.model_dir and (self.model_dir / p_obj).exists():
                return str(self.model_dir / p_obj)
            return str(proj_rel if not p_obj.is_absolute() else p_obj)

        ident = identifier if identifier is not None else self.model_name
        if not ident:
            return ""

        path_obj = Path(ident)

        # 2. 直接绝对路径
        if path_obj.is_absolute() and path_obj.exists():
            return str(path_obj)

        # 3. 相对项目根目录
        project_rel = PROJECT_ROOT / path_obj
        if project_rel.exists():
            return str(project_rel)

        # 4. 在 model_dir 下探测
        if self.model_dir:
            p1 = self.model_dir / path_obj
            if p1.exists():
                return str(p1)

            pure_name = ident.split("/")[-1]
            p2 = self.model_dir / pure_name
            if p2.exists():
                return str(p2)

            p3 = self.model_dir / self.engine_name / pure_name
            if p3.exists():
                return str(p3)

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
