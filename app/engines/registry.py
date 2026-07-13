import logging
from dataclasses import dataclass

from app.core.config import app_config
from app.engines.base import ASREngine
from app.engines.whisper_engine import WhisperEngine
from app.engines.firered_engine import FireRedEngine
from app.engines.openai_engine import OpenAIEngine
from app.engines.mimo_engine import MiMoEngine
from app.engines.whisperlivekit_engine import WhisperLiveKitEngine

logger = logging.getLogger(__name__)

# 引擎类型名 → 引擎类（不变，这是底层映射）
_engine_classes: dict[str, type[ASREngine]] = {
    "faster-whisper": WhisperEngine,
    "firered": FireRedEngine,
    "openai": OpenAIEngine,
    "mimo": MiMoEngine,
    "whisperlivekit": WhisperLiveKitEngine,
}


@dataclass
class LoadedEngine:
    """已加载引擎的元信息。"""
    engine: ASREngine
    provider_name: str
    engine_name: str
    model_name: str
    device: str
    compute_type: str
    streaming: bool


# key = "provider_name/model_name/device/compute_type"
_loaded: dict[str, LoadedEngine] = {}


def _make_key(provider_name: str, model_name: str, device: str = "", compute_type: str = "") -> str:
    if device and compute_type:
        return f"{provider_name}/{model_name}/{device}/{compute_type}"
    return f"{provider_name}/{model_name}"


def get_engine(name: str | None = None) -> ASREngine:
    """获取 ASR 引擎实例。

    name 是 Provider 名（如 "whisper1"），通过 provider config 中的 engine 字段
    确定底层引擎类型。

    支持格式：
    - "whisper1" → 使用该 provider 的配置
    - "whisper1/medium" → 使用指定模型的实例
    - "whisper1/medium/cpu/int8" → 使用精确配置的实例
    """
    name = name or app_config.default_provider

    # 支持完整路径 "provider/model/device/compute_type"
    parts = name.split("/")
    if len(parts) == 4:
        key = name
        if key in _loaded:
            return _loaded[key].engine
        return _ensure_engine(parts[0])

    # 支持 "provider/model" 格式
    if len(parts) == 2:
        provider_name, model_name = parts
        prefix = f"{provider_name}/{model_name}"
        for k, le in _loaded.items():
            if k.startswith(prefix):
                return le.engine
        return _ensure_engine(provider_name)

    # 仅 provider 名：查找该 provider 的任意已加载实例
    for k, le in _loaded.items():
        if k.startswith(f"{name}/"):
            return le.engine
    return _ensure_engine(name)


def _ensure_engine(provider_name: str) -> ASREngine:
    """确保引擎已加载，未加载则用 provider 配置创建。"""
    config = app_config.get_provider_config(provider_name)

    if config.engine_name not in _engine_classes:
        raise ValueError(f"未知引擎类型: {config.engine_name}，可用: {list(_engine_classes)}")

    key = _make_key(provider_name, config.model_name, config.device, config.compute_type)
    if key in _loaded:
        return _loaded[key].engine

    engine = _engine_classes[config.engine_name](config)
    _loaded[key] = LoadedEngine(
        engine=engine,
        provider_name=provider_name,
        engine_name=config.engine_name,
        model_name=config.model_name,
        device=config.device,
        compute_type=config.compute_type,
        streaming=(config.engine_name == "whisperlivekit"),
    )
    return engine


def get_loaded_engines() -> dict[str, LoadedEngine]:
    """返回所有已加载引擎。"""
    return dict(_loaded)


def register_engine(name: str, engine_cls: type[ASREngine]):
    _engine_classes[name] = engine_cls
