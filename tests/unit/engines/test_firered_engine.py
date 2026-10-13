"""FireRedEngine (基于 sherpa-onnx OfflineRecognizer.from_fire_red_asr) 单元测试。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest

from server.core.config import EngineConfig
from server.engines.firered_engine import FireRedEngine

pytestmark = pytest.mark.unit


def test_firered_engine_validate_and_load_via_sherpa_onnx(tmp_path: Path, monkeypatch):
    model_dir = tmp_path / "firered-onnx"
    model_dir.mkdir()
    (model_dir / "encoder.int8.onnx").write_bytes(b"enc")
    (model_dir / "decoder.int8.onnx").write_bytes(b"dec")
    (model_dir / "tokens.txt").write_text("a 0\n", encoding="utf-8")

    cfg = EngineConfig(
        "firered",
        {
            "enable": True,
            "engine": "firered",
            "load": {
                "model_path": str(model_dir),
                "num_threads": 2,
            },
        },
    )

    called_kwargs = {}

    class DummyStream:
        def __init__(self):
            self.result = SimpleNamespace(text="  你好 FireRed  ")
            self.accepted = None

        def accept_waveform(self, sample_rate, samples):
            self.accepted = (sample_rate, len(samples))

    class DummyRecognizer:
        def create_stream(self):
            return DummyStream()

        def decode_stream(self, stream):
            pass

    def fake_from_fire_red_asr(**kwargs):
        called_kwargs.update(kwargs)
        return DummyRecognizer()

    import sherpa_onnx

    monkeypatch.setattr(
        sherpa_onnx.OfflineRecognizer, "from_fire_red_asr", staticmethod(fake_from_fire_red_asr)
    )

    engine = FireRedEngine(cfg, lazy_load=True)
    assert engine.is_loaded is False

    engine.load()
    assert engine.is_loaded is True
    assert called_kwargs["encoder"].endswith("encoder.int8.onnx")
    assert called_kwargs["decoder"].endswith("decoder.int8.onnx")
    assert called_kwargs["tokens"].endswith("tokens.txt")

    dummy_chunk = SimpleNamespace(
        samples=np.zeros(16000, dtype=np.float32),
        sample_rate=16000,
    )
    text, segs = engine._transcribe_chunk(dummy_chunk)
    assert text == "你好 FireRed"
    assert segs == []

    engine.unload()
    assert engine.is_loaded is False
