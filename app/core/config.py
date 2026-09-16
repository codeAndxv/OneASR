from pathlib import Path

import yaml
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).parent.parent.parent


class EngineConfig:
    def __init__(self, name: str, config: dict, model_dir: Path | None):
        self.name = name
        self.engine_name = config.get("engine", name)
        self.type = config.get("type", "local")
        self.model_name = config.get("model_name", "")
        self.device = config.get("device", "cpu")
        self.compute_type = config.get("compute_type", "float32")
        self.max_duration = config.get("max_duration")
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
        # 模型路径
        self.model_path = model_dir / self.engine_name if model_dir else None


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
