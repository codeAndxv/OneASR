import logging
from dataclasses import dataclass

from app.core.config import app_config, EngineConfig
from app.engines.base import ASREngine
from app.engines.whisper_engine import WhisperEngine
from app.engines.firered_engine import FireRedEngine
from app.engines.openai_engine import OpenAIEngine
from app.engines.mimo_engine import MiMoEngine
from app.engines.wlk_engine import WLKEngine

logger = logging.getLogger(__name__)

_engine_classes: dict[str, type[ASREngine]] = {
    "faster-whisper": WhisperEngine,
    "firered": FireRedEngine,
    "openai": OpenAIEngine,
    "mimo": MiMoEngine,
    "wlk": WLKEngine,
}


@dataclass
class LoadedEngine:
    """已加载引擎的元信息。"""
    engine: ASREngine
    engine_name: str
    model_name: str
    device: str
    compute_type: str
    streaming: bool


# key = "engine_name/model_name/device/compute_type"（如 "faster-whisper/medium/cpu/int8"）
_loaded: dict[str, LoadedEngine] = {}


def _make_key(engine_name: str, model_name: str, device: str = "", compute_type: str = "") -> str:
    if device and compute_type:
        return f"{engine_name}/{model_name}/{device}/{compute_type}"
    return f"{engine_name}/{model_name}"


def get_engine(name: str | None = None) -> ASREngine:
    """获取 ASR 引擎实例。

    支持格式：
    - "faster-whisper" → 使用该引擎的任意已加载实例
    - "faster-whisper/medium" → 使用指定模型的实例
    - "faster-whisper/medium/cpu/int8" → 使用精确配置的实例
    """
    name = name or app_config.default_engine

    # 支持完整路径 "engine/model/device/compute_type"
    parts = name.split("/")
    if len(parts) == 4:
        key = name
        if key in _loaded:
            return _loaded[key].engine
        return _ensure_engine(parts[0])

    # 支持 "engine/model" 格式
    if len(parts) == 2:
        engine_name, model_name = parts
        prefix = f"{engine_name}/{model_name}"
        for k, le in _loaded.items():
            if k.startswith(prefix):
                return le.engine
        return _ensure_engine(engine_name)

    # 仅引擎名：查找该引擎的任意已加载实例
    for k, le in _loaded.items():
        if k.startswith(f"{name}/"):
            return le.engine
    return _ensure_engine(name)


def _ensure_engine(name: str) -> ASREngine:
    """确保引擎已加载，未加载则用默认配置创建。"""
    if name not in _engine_classes:
        raise ValueError(f"未知引擎: {name}，可用: {list(_engine_classes)}")
    config = app_config.get_engine_config(name)
    key = _make_key(name, config.model_name, config.device, config.compute_type)
    if key in _loaded:
        return _loaded[key].engine
    engine = _engine_classes[name](config)
    _loaded[key] = LoadedEngine(
        engine=engine,
        engine_name=name,
        model_name=config.model_name,
        device=config.device,
        compute_type=config.compute_type,
        streaming=(name == "wlk"),
    )
    return engine


def load_engine(
    engine_name: str,
    model_name: str,
    device: str = "cpu",
    compute_type: str = "int8",
) -> LoadedEngine:
    """加载指定引擎和模型。

    如果相同配置（engine + model + device + compute_type）已加载则直接返回。

    Args:
        engine_name: 引擎名（如 "faster-whisper"）
        model_name: 模型名（如 "medium", "large-v3"）
        device: 设备（"cpu" 或 "cuda"）
        compute_type: 计算精度（"int8", "float16", "int8_float16" 等）

    Returns:
        LoadedEngine 实例
    """
    if engine_name not in _engine_classes:
        raise ValueError(f"未知引擎: {engine_name}，可用: {list(_engine_classes)}")

    key = _make_key(engine_name, model_name, device, compute_type)
    if key in _loaded:
        logger.info("相同配置已加载，直接返回: %s", key)
        return _loaded[key]

    logger.info("正在加载引擎: %s, model=%s, device=%s, compute_type=%s",
                engine_name, model_name, device, compute_type)

    # 构建 EngineConfig
    base_config = app_config.engines.get(engine_name)
    config = EngineConfig(
        name=engine_name,
        config={
            "type": base_config.type if base_config else "local",
            "model_name": model_name,
            "device": device,
            "compute_type": compute_type,
        },
        model_dir=app_config.model_dir,
    )

    engine = _engine_classes[engine_name](config)
    loaded = LoadedEngine(
        engine=engine,
        engine_name=engine_name,
        model_name=model_name,
        device=device,
        compute_type=compute_type,
        streaming=(engine_name == "wlk"),
    )
    _loaded[key] = loaded
    logger.info("引擎加载完成: %s", key)
    return loaded


def get_loaded_engines() -> dict[str, LoadedEngine]:
    """返回所有已加载引擎。"""
    return dict(_loaded)


def register_engine(name: str, engine_cls: type[ASREngine]):
    _engine_classes[name] = engine_cls
