from app.core.config import settings
from app.engines.base import ASREngine
from app.engines.whisper_engine import WhisperEngine

_engine_registry: dict[str, type[ASREngine]] = {
    "whisper": WhisperEngine,
}

_instances: dict[str, ASREngine] = {}


def _create_whisper_engine() -> WhisperEngine:
    return WhisperEngine(
        model_size=settings.whisper_model_size,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )


_engine_factories: dict[str, callable] = {
    "whisper": _create_whisper_engine,
}


def get_engine(name: str | None = None) -> ASREngine:
    """获取 ASR 引擎实例。未指定名称时使用默认引擎。"""
    name = name or settings.default_engine
    if name not in _engine_registry:
        raise ValueError(f"未知引擎: {name}，可用: {list(_engine_registry)}")
    if name not in _instances:
        factory = _engine_factories.get(name)
        _instances[name] = factory() if factory else _engine_registry[name]()
    return _instances[name]


def register_engine(name: str, engine_cls: type[ASREngine], factory: callable = None):
    _engine_registry[name] = engine_cls
    if factory:
        _engine_factories[name] = factory
