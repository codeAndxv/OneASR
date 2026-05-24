from app.core.config import app_config, EngineConfig
from app.engines.base import ASREngine
from app.engines.whisper_engine import WhisperEngine
from app.engines.firered_engine import FireRedEngine

_engine_classes: dict[str, type[ASREngine]] = {
    "whisper": WhisperEngine,
    "firered": FireRedEngine,
}

_instances: dict[str, ASREngine] = {}


def get_engine(name: str | None = None) -> ASREngine:
    """获取 ASR 引擎实例。未指定名称时使用默认引擎。"""
    name = name or app_config.default_engine
    if name not in _engine_classes:
        raise ValueError(f"未知引擎: {name}，可用: {list(_engine_classes)}")
    if name not in _instances:
        config = app_config.get_engine_config(name)
        _instances[name] = _engine_classes[name](config)
    return _instances[name]


def register_engine(name: str, engine_cls: type[ASREngine]):
    _engine_classes[name] = engine_cls
