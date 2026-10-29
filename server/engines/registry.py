"""ASR 引擎注册表与生命周期管理器（Ollama 风格 keep_alive 空闲释放 + LRU 容量上限 + 引用计数保护）。"""

import inspect
import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

from server.core.config import DRIVER_ALIAS_MAP, app_config
from server.engines.base import ASREngine, release_hardware_memory
from server.engines.firered_engine import FireRedEngine
from server.engines.funasr_engine import FunASREngine
from server.engines.openai_engine import OpenAIEngine
from server.engines.qwen_engine import QwenEngine
from server.engines.sherpa_onnx_engine import SherpaOnnxEngine
from server.engines.whisper_engine import WhisperEngine

logger = logging.getLogger(__name__)

# 核心模型系列驱动 → 引擎实现类（本地模型系列 + 统一云端服务）
_engine_classes: dict[str, type[ASREngine]] = {
    "xasr": SherpaOnnxEngine,
    "whisper": WhisperEngine,
    "funasr": FunASREngine,
    "qwen": QwenEngine,
    "firered": FireRedEngine,
    "openai": OpenAIEngine,
}



@dataclass
class LoadedEngine:
    """已加载引擎的运行态元信息。"""
    engine: ASREngine
    model_id: str
    engine_name: str
    model_name: str
    device: str
    compute_type: str
    streaming: bool
    keep_alive: int = 600
    preload: bool = False
    active_tasks: int = 0
    loaded_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)

    @property
    def provider_name(self) -> str:
        """Backward-compatible alias for model_id."""
        return self.model_id


# key = "model_id/model_name/device/compute_type"
_loaded: dict[str, LoadedEngine] = {}
# 已通过配置校验的轻量引擎壳实例（lazy_load=True，未加载权重）
_standby: dict[str, ASREngine] = {}
# 可重入线程锁，防止并发重复实例化同一大模型或读写竞争
_registry_lock = threading.RLock()


def _make_key(model_id: str, model_name: str, device: str = "", compute_type: str = "") -> str:
    if device and compute_type:
        return f"{model_id}/{model_name}/{device}/{compute_type}"
    return f"{model_id}/{model_name}"


def _resolve_model_name(name: str | None) -> str:
    if not name:
        return next(iter(app_config.models))
    return name.split("/")[0]


_resolve_provider_name = _resolve_model_name


def _find_loaded_entry(name: str) -> tuple[str, LoadedEngine] | tuple[None, None]:
    parts = name.split("/")
    if len(parts) == 4 and name in _loaded:
        return name, _loaded[name]
    if len(parts) == 2:
        prefix = f"{parts[0]}/{parts[1]}"
        for k, le in _loaded.items():
            if k.startswith(prefix):
                return k, le
    model_id = parts[0]
    for k, le in _loaded.items():
        if k == model_id or k.startswith(f"{model_id}/"):
            return k, le
    return None, None


def _instantiate_engine(model_id: str, lazy_load: bool = False) -> ASREngine:
    config = app_config.get_model_config(model_id)
    engine_name = DRIVER_ALIAS_MAP.get(config.engine_name, config.engine_name)
    if engine_name not in _engine_classes:
        raise ValueError(f"未知引擎类型: {config.engine_name}，可用: {list(_engine_classes)}")

    engine_cls = _engine_classes[engine_name]
    sig = inspect.signature(engine_cls.__init__)
    if "lazy_load" in sig.parameters:
        return engine_cls(config, lazy_load=lazy_load)
    return engine_cls(config)


def validate_model(model_id: str) -> ASREngine:
    """仅校验 Model 配置与本地模型文件是否存在（不加载大模型权重进内存）。"""
    with _registry_lock:
        _, existing = _find_loaded_entry(model_id)
        if existing is not None:
            existing.engine.validate_config()
            return existing.engine

        if model_id in _standby:
            _standby[model_id].validate_config()
            return _standby[model_id]

        engine = _instantiate_engine(model_id, lazy_load=True)
        _standby[model_id] = engine
        return engine


validate_provider = validate_model


def _evict_lru_if_needed(target_model_id: str) -> list[str]:
    """当非常驻本地大模型达到 max_loaded_models 上限时，按 LRU 自动淘汰最久未使用的空闲模型。"""
    max_models = app_config.model_manager.max_loaded_models
    if max_models <= 0:
        return []

    target_cfg = app_config.get_model_config(target_model_id)
    # 若目标模型本身是常驻小模型 (keep_alive == -1) 或云端模型，不触发淘汰
    if target_cfg.keep_alive == -1 or target_cfg.type == "cloud":
        return []

    evictable: list[tuple[str, LoadedEngine]] = []
    loaded_heavy_count = 0

    for k, le in _loaded.items():
        if le.model_id == target_model_id:
            continue
        cfg = app_config.models.get(le.model_id)
        is_cloud = cfg and cfg.type == "cloud"
        if le.keep_alive != -1 and not is_cloud:
            loaded_heavy_count += 1
            if le.active_tasks <= 0:
                evictable.append((k, le))

    evicted_names: list[str] = []
    if loaded_heavy_count >= max_models and evictable:
        # 按 last_used_at 从旧到新排序
        evictable.sort(key=lambda item: item[1].last_used_at)
        need_to_evict = loaded_heavy_count - max_models + 1
        for k, le in evictable[:need_to_evict]:
            logger.info(
                "[ModelManager] 触发 LRU 容量回收 (上限=%d): 卸载空闲模型 %s (上次使用 %.1fs 前)",
                max_models, le.model_id, time.time() - le.last_used_at,
            )
            le.engine.unload()
            _standby[le.model_id] = le.engine
            _loaded.pop(k, None)
            evicted_names.append(le.model_id)

    return evicted_names


def get_engine(name: str | None = None) -> ASREngine:
    """获取已加载权重的 ASR 引擎实例（若处于待命/已卸载状态则自动加载权重并刷新活跃时间）。"""
    name = name or next(iter(app_config.models))
    model_id = _resolve_model_name(name)

    with _registry_lock:
        _, loaded_entry = _find_loaded_entry(name)
        if loaded_entry is not None:
            if not loaded_entry.engine.is_loaded:
                loaded_entry.engine.load()
                loaded_entry.loaded_at = time.time()
            loaded_entry.last_used_at = time.time()
            return loaded_entry.engine

        return _ensure_engine(model_id)


def _ensure_engine(model_id: str) -> ASREngine:
    """确保引擎权重已加载进内存，包含并发锁与 LRU 容量回收。"""
    with _registry_lock:
        config = app_config.get_model_config(model_id)
        engine_name = DRIVER_ALIAS_MAP.get(config.engine_name, config.engine_name)

        if engine_name not in _engine_classes:
            raise ValueError(f"未知引擎类型: {config.engine_name}，可用: {list(_engine_classes)}")

        key = _make_key(model_id, config.model_name, config.device, config.compute_type)
        if key in _loaded:
            le = _loaded[key]
            if not le.engine.is_loaded:
                le.engine.load()
                le.loaded_at = time.time()
            le.last_used_at = time.time()
            return le.engine

        # 检查是否超出最大并发常驻大模型数，必要时先淘汰空闲旧模型释放内存
        _evict_lru_if_needed(model_id)

        # 优先复用已在 standby 中通过校验的实例
        engine = _standby.pop(model_id, None)
        if engine is None:
            engine = _instantiate_engine(model_id, lazy_load=False)
        else:
            engine.load()

        now = time.time()
        _loaded[key] = LoadedEngine(
            engine=engine,
            model_id=model_id,
            engine_name=config.engine_name,
            model_name=config.model_name,
            device=config.device,
            compute_type=config.compute_type,
            streaming="RealtimeASR" in config.categories or config.engine_name == "xasr",
            keep_alive=config.keep_alive,
            preload=config.preload,
            active_tasks=0,
            loaded_at=now,
            last_used_at=now,
        )
        return engine


@contextmanager
def acquire_engine(name: str | None = None, engine_getter=None):
    """获取引擎并自动维护 active_tasks 引用计数与 keep_alive=0 即刻卸载。

    当 active_tasks > 0 时，后台空闲回收器与 LRU 绝不会卸载该模型。
    """
    getter = engine_getter or get_engine
    eng = getter(name)
    model_id = _resolve_model_name(name)

    with _registry_lock:
        _, entry = _find_loaded_entry(model_id)
        if entry is not None:
            entry.active_tasks += 1
            entry.last_used_at = time.time()

    try:
        yield eng
    finally:
        with _registry_lock:
            key, entry = _find_loaded_entry(model_id)
            if entry is not None:
                entry.active_tasks = max(0, entry.active_tasks - 1)
                entry.last_used_at = time.time()
                if entry.keep_alive == 0 and entry.active_tasks == 0:
                    logger.info("[ModelManager] 模型 %s 配置为 keep_alive=0，任务完成立即卸载释放内存", model_id)
                    entry.engine.unload()
                    _standby[entry.model_id] = entry.engine
                    if key:
                        _loaded.pop(key, None)


def unload_engine(name: str, force: bool = False) -> bool:
    """显式卸载指定 Model 的模型并释放内存。

    若模型当前未加载返回 False；若正在被任务使用且 force=False 则抛出 RuntimeError。
    """
    model_id = _resolve_model_name(name)
    with _registry_lock:
        key, entry = _find_loaded_entry(model_id)
        if entry is None:
            return False

        if entry.active_tasks > 0 and not force:
            raise RuntimeError(
                f"模型 '{model_id}' 当前有 {entry.active_tasks} 个活跃任务正在运行，无法卸载"
            )

        logger.info("[ModelManager] 正在卸载模型: %s", model_id)
        entry.engine.unload()
        _standby[entry.model_id] = entry.engine
        if key:
            _loaded.pop(key, None)
        release_hardware_memory()
        return True


def unload_idle_engines(now: float | None = None) -> list[str]:
    """扫描并卸载所有超过 keep_alive 空闲时间且无活跃任务的模型。返回被卸载的 model_id 列表。"""
    now = now if now is not None else time.time()
    unloaded: list[str] = []

    with _registry_lock:
        for key, entry in list(_loaded.items()):
            # keep_alive < 0 表示常驻不自动卸载；active_tasks > 0 表示正在推理中不可卸载
            if entry.keep_alive < 0 or entry.active_tasks > 0:
                continue
            idle_seconds = now - entry.last_used_at
            if idle_seconds >= entry.keep_alive:
                logger.info(
                    "[ModelManager] 模型 %s 已空闲 %.1fs (超过 keep_alive=%ds)，自动卸载释放内存",
                    entry.model_id, idle_seconds, entry.keep_alive,
                )
                entry.engine.unload()
                _standby[entry.model_id] = entry.engine
                _loaded.pop(key, None)
                unloaded.append(entry.model_id)

    if unloaded:
        release_hardware_memory()
    return unloaded


def unload_all(force: bool = True) -> list[str]:
    """卸载所有已加载模型（用于服务关闭阶段）。"""
    unloaded: list[str] = []
    with _registry_lock:
        for key, entry in list(_loaded.items()):
            if entry.active_tasks > 0 and not force:
                continue
            entry.engine.unload()
            _standby[entry.model_id] = entry.engine
            _loaded.pop(key, None)
            unloaded.append(entry.model_id)
    if unloaded:
        release_hardware_memory()
    return unloaded


def get_model_runtime_status(model_id: str) -> dict:
    """获取指定 Model 的实时运行状态（供 /v1/x/models 和 /v1/models 返回）。"""
    cfg = app_config.models.get(model_id)
    with _registry_lock:
        _, entry = _find_loaded_entry(model_id)
        if entry is not None and entry.engine.is_loaded:
            return {
                "loaded": True,
                "active_tasks": entry.active_tasks,
                "keep_alive": entry.keep_alive,
                "preload": entry.preload,
                "loaded_at": int(entry.loaded_at),
                "last_used_at": int(entry.last_used_at),
            }
        return {
            "loaded": False,
            "active_tasks": 0,
            "keep_alive": cfg.keep_alive if cfg else 600,
            "preload": cfg.preload if cfg else False,
            "loaded_at": None,
            "last_used_at": None,
        }


get_provider_runtime_status = get_model_runtime_status


def get_loaded_engines() -> dict[str, LoadedEngine]:
    """返回所有当前已加载权重的引擎。"""
    with _registry_lock:
        return dict(_loaded)


def register_engine(name: str, engine_cls: type[ASREngine]):
    with _registry_lock:
        _engine_classes[name] = engine_cls
