"""QwenEngine 单元测试（验证语言映射与 context 提示词透传）。"""

from pathlib import Path
from unittest.mock import MagicMock
import pytest

from server.core.config import EngineConfig
from server.engines.qwen_engine import QwenEngine

pytestmark = pytest.mark.unit


def test_normalize_qwen_language():
    norm = QwenEngine.normalize_qwen_language
    assert norm(None) is None
    assert norm("") is None
    assert norm("auto") is None
    assert norm("zh") == "Chinese"
    assert norm("zh-CN") == "Chinese"
    assert norm("zh-HK") == "Cantonese"
    assert norm("yue") == "Cantonese"
    assert norm("en") == "English"
    assert norm("en-US") == "English"
    assert norm("ja") == "Japanese"
    assert norm("ko") == "Korean"
    assert norm("Chinese") == "Chinese"
    assert norm("English") == "English"


def test_qwen_transcribe_sync_passes_canonical_language_and_context(tmp_path: Path):
    cfg = EngineConfig(
        "qwen3-asr",
        {
            "model_name": "Qwen/Qwen3-ASR-0.6B",
            "model_path": str(tmp_path),
            "device": "cpu",
        },
    )
    engine = QwenEngine(cfg, lazy_load=True)
    mock_model = MagicMock()
    mock_res = MagicMock()
    mock_res.text = "测试 Qwen 识别"
    mock_res.time_stamps = None
    mock_model.transcribe.return_value = [mock_res]
    engine._model = mock_model

    eff_lang = QwenEngine.normalize_qwen_language("zh")
    text, segments = engine._transcribe_sync(
        "dummy.wav",
        prompt="OneASR, DuRT",
        language=eff_lang,
    )

    assert text == "测试 Qwen 识别"
    call_kwargs = mock_model.transcribe.call_args[1]
    assert call_kwargs["language"] == "Chinese"
    assert call_kwargs["context"] == "OneASR, DuRT"
    assert "prompt" not in call_kwargs
