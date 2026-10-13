"""模型加载与释放生命周期管理（ModelManager）单元测试。

验证点：
1. keep_alive 时间表达式解析 ("10m", "1h", "30s", -1, 0)
2. validate_provider 零内存待命校验 vs get_engine 按需加载
3. acquire_engine 引用计数保护（正在推理时禁止被 idle 巡检或非强制 unload 卸载）
4. keep_alive=0 任务结束即刻卸载
5. unload_idle_engines 空闲超时自动释放（keep_alive=-1 常驻模型豁免）
6. max_loaded_models LRU 容量上限自动淘汰最久未用空闲模型
"""

import time
import pytest

from server.core.config import EngineConfig, app_config, parse_keep_alive_seconds
from server.engines import registry
from server.engines.base import ASREngine
from server.schemas.audio import Segment

pytestmark = pytest.mark.unit


class DummyLifecycleEngine(ASREngine):
    """用于测试生命周期状态机的轻量级引擎。"""

    def __init__(self, config: EngineConfig, lazy_load: bool = False):
        self.config = config
        self.model = None
        self.validate_calls = 0
        self.load_calls = 0
        self.unload_calls = 0
        self.validate_config()
        if not lazy_load:
            self.load()

    def validate_config(self) -> None:
        self.validate_calls += 1

    def load(self) -> None:
        if self.model is None:
            self.load_calls += 1
            self.model = {"weights": f"loaded-{self.config.name}"}

    def unload(self) -> None:
        if self.model is not None:
            self.unload_calls += 1
            self.model = None

    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    async def transcribe_file(self, audio_data: bytes) -> tuple[str, list[Segment]]:
        self.load()
        return "ok", [Segment(start=0.0, end=1.0, text="ok")]

    async def transcribe_stream(self, audio_chunk: bytes) -> str | None:
        return None

    async def stream_finalize(self) -> str:
        return ""


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch):
    """隔离全局 registry 状态与测试虚拟 Provider，防止影响其他测试。"""
    saved_loaded = dict(registry._loaded)
    saved_standby = dict(registry._standby)
    saved_providers = dict(app_config.providers)
    saved_max = app_config.model_manager.max_loaded_models

    registry._loaded.clear()
    registry._standby.clear()
    registry.register_engine("dummy-lifecycle", DummyLifecycleEngine)

    app_config.providers["dummy-pinned"] = EngineConfig(
        "dummy-pinned",
        {
            "engine": "dummy-lifecycle",
            "preload": True,
            "keep_alive": -1,
            "load": {"model_name": "pinned-v1", "device": "cpu"},
            "properties": {"categories": ["RealtimeASR"]},
        },
    )
    app_config.providers["dummy-heavy-1"] = EngineConfig(
        "dummy-heavy-1",
        {
            "engine": "dummy-lifecycle",
            "preload": False,
            "keep_alive": 60,
            "load": {"model_name": "heavy-1", "device": "cpu"},
            "properties": {"categories": ["FileASR"]},
        },
    )
    app_config.providers["dummy-heavy-2"] = EngineConfig(
        "dummy-heavy-2",
        {
            "engine": "dummy-lifecycle",
            "preload": False,
            "keep_alive": 60,
            "load": {"model_name": "heavy-2", "device": "cpu"},
            "properties": {"categories": ["FileASR"]},
        },
    )
    app_config.providers["dummy-oneshot"] = EngineConfig(
        "dummy-oneshot",
        {
            "engine": "dummy-lifecycle",
            "preload": False,
            "keep_alive": 0,
            "load": {"model_name": "oneshot", "device": "cpu"},
            "properties": {"categories": ["FileASR"]},
        },
    )

    yield

    registry._loaded.clear()
    registry._loaded.update(saved_loaded)
    registry._standby.clear()
    registry._standby.update(saved_standby)
    app_config.providers.clear()
    app_config.providers.update(saved_providers)
    app_config.model_manager.max_loaded_models = saved_max


def test_parse_keep_alive_seconds():
    assert parse_keep_alive_seconds(-1) == -1
    assert parse_keep_alive_seconds("forever") == -1
    assert parse_keep_alive_seconds(0) == 0
    assert parse_keep_alive_seconds("0s") == 0
    assert parse_keep_alive_seconds("30s") == 30
    assert parse_keep_alive_seconds("10m") == 600
    assert parse_keep_alive_seconds("1.5h") == 5400
    assert parse_keep_alive_seconds(300) == 300


def test_validate_provider_does_not_load_weights():
    """validate_provider 仅校验配置并进入待命态，不加载模型权重。"""
    eng = registry.validate_provider("dummy-heavy-1")
    assert eng.is_loaded is False
    assert eng.load_calls == 0

    rt = registry.get_provider_runtime_status("dummy-heavy-1")
    assert rt["loaded"] is False

    # 当真正调用 get_engine 时才加载权重
    loaded_eng = registry.get_engine("dummy-heavy-1")
    assert loaded_eng is eng
    assert loaded_eng.is_loaded is True
    assert loaded_eng.load_calls == 1
    assert registry.get_provider_runtime_status("dummy-heavy-1")["loaded"] is True


def test_reference_counting_protects_active_model():
    """正在使用中的模型 (active_tasks > 0) 绝不会被超时回收或非强制卸载。"""
    with registry.acquire_engine("dummy-heavy-1") as eng:
        assert eng.is_loaded is True
        rt = registry.get_provider_runtime_status("dummy-heavy-1")
        assert rt["active_tasks"] == 1

        # 即使时间过去了 1000 秒，因 active_tasks == 1，idle 巡检也不会卸载它
        unloaded = registry.unload_idle_engines(now=time.time() + 1000)
        assert "dummy-heavy-1" not in unloaded
        assert eng.is_loaded is True

        # 非强制手动卸载应抛出 RuntimeError
        with pytest.raises(RuntimeError, match="活跃任务"):
            registry.unload_engine("dummy-heavy-1", force=False)

    # 退出上下文后 active_tasks 归零
    assert registry.get_provider_runtime_status("dummy-heavy-1")["active_tasks"] == 0


def test_keep_alive_zero_unloads_immediately_after_use():
    """keep_alive=0 的模型在 acquire_engine 退出时立即卸载释放内存。"""
    with registry.acquire_engine("dummy-oneshot") as eng:
        assert eng.is_loaded is True

    assert eng.is_loaded is False
    assert eng.unload_calls == 1
    assert registry.get_provider_runtime_status("dummy-oneshot")["loaded"] is False


def test_ttl_idle_reaper_unloads_expired_but_keeps_pinned():
    """超过 keep_alive 的空闲模型自动卸载，而 keep_alive=-1 的常驻模型永久保留。"""
    pinned = registry.get_engine("dummy-pinned")
    heavy1 = registry.get_engine("dummy-heavy-1")

    assert pinned.is_loaded is True
    assert heavy1.is_loaded is True

    # 30 秒后（未达 60s keep_alive）：两者都保持加载
    unloaded_early = registry.unload_idle_engines(now=time.time() + 30)
    assert unloaded_early == []
    assert heavy1.is_loaded is True

    # 65 秒后（超过 60s keep_alive）：dummy-heavy-1 被自动卸载，dummy-pinned 依然常驻
    unloaded_expired = registry.unload_idle_engines(now=time.time() + 65)
    assert unloaded_expired == ["dummy-heavy-1"]
    assert heavy1.is_loaded is False
    assert pinned.is_loaded is True


def test_lru_capacity_evicts_oldest_idle_heavy_model():
    """当本地非常驻模型达到 max_loaded_models=1 上限时，加载新模型自动淘汰旧空闲模型。"""
    app_config.model_manager.max_loaded_models = 1

    # 常驻模型 (keep_alive=-1) 不占非常驻配额
    pinned = registry.get_engine("dummy-pinned")
    heavy1 = registry.get_engine("dummy-heavy-1")
    assert pinned.is_loaded is True
    assert heavy1.is_loaded is True

    # 加载第 2 个大模型 dummy-heavy-2，应自动卸载空闲的 dummy-heavy-1
    heavy2 = registry.get_engine("dummy-heavy-2")
    assert heavy2.is_loaded is True
    assert heavy1.is_loaded is False
    assert pinned.is_loaded is True
