"""测试模型路径自动推导、本地存在性校验与错误下载提示。"""

from unittest.mock import MagicMock, patch
import pytest

from server.core.config import EngineConfig, PROJECT_ROOT
from server.engines.funasr_engine import FunASREngine
from server.engines.qwen_engine import QwenEngine
from server.engines.whisper_engine import WhisperEngine
from server.engines.xasr_engine import XASREngine

pytestmark = pytest.mark.unit


def test_engine_config_auto_derives_paths_from_model_name():
    """当未显式配置 *_path 时，EngineConfig 必须根据 model_name 自动推导 data/models/<repo_name> 路径。"""
    # 1. Faster-Whisper
    w_cfg = EngineConfig("faster-whisper", {"engine": "faster-whisper", "load": {"model_name": "Systran/faster-whisper-medium"}})
    assert w_cfg.model_path == "data/models/faster-whisper-medium"
    assert w_cfg.resolve_path(w_cfg.model_path) == PROJECT_ROOT / "data/models/faster-whisper-medium"

    # 2. Qwen + ForcedAligner
    q_cfg = EngineConfig(
        "qwen",
        {
            "engine": "qwen",
            "load": {
                "model_name": "Qwen/Qwen3-ASR-1.7B",
                "forced_aligner_name": "Qwen/Qwen3-ForcedAligner-0.6B",
            },
        },
    )
    assert q_cfg.model_path == "data/models/Qwen3-ASR-1.7B"
    assert q_cfg.forced_aligner_path == "data/models/Qwen3-ForcedAligner-0.6B"

    # 3. FunASR + VAD
    f_cfg = EngineConfig(
        "funasr",
        {
            "engine": "funasr",
            "load": {
                "model_name": "iic/SenseVoiceSmall",
                "vad_model": "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
            },
        },
    )
    assert f_cfg.model_path == "data/models/SenseVoiceSmall"
    assert f_cfg.vad_model_path == "data/models/speech_fsmn_vad_zh-cn-16k-common-pytorch"

    # 4. X-ASR
    x_cfg = EngineConfig("xasr", {"engine": "xasr", "load": {"model_name": "Gilgamesh-J/X-ASR-zh-en"}})
    assert x_cfg.tokens_path == "data/models/chunk-160ms-model/tokens.txt"
    assert x_cfg.encoder_path == "data/models/chunk-160ms-model/encoder-160ms.onnx"
    assert x_cfg.decoder_path == "data/models/chunk-160ms-model/decoder-160ms.onnx"
    assert x_cfg.joiner_path == "data/models/chunk-160ms-model/joiner-160ms.onnx"


def test_engine_config_explicit_paths():
    """测试显式指定 model_path 时优先使用显式路径。"""
    cfg_data = {
        "engine": "faster-whisper",
        "load": {
            "model_name": "Systran/faster-whisper-medium",
            "model_path": "models/medium",
        },
    }
    cfg = EngineConfig("faster-whisper", cfg_data)
    assert cfg.model_path == "models/medium"
    assert cfg.resolve_path(cfg.model_path) == PROJECT_ROOT / "models/medium"


def test_whisper_nonexistent_model_raises():
    """当 faster-whisper 推导或配置的本地目录不存在时，必须立即抛出 RuntimeError 并包含 CLI 下载命令。"""
    cfg_data = {
        "engine": "faster-whisper",
        "load": {
            "model_name": "Systran/faster-whisper-non-existent-xyz",
        },
    }
    cfg = EngineConfig("whisper-test", cfg_data)
    with pytest.raises(RuntimeError) as exc_info:
        WhisperEngine(cfg)

    err_text = str(exc_info.value)
    assert "配置的模型路径不存在" in err_text
    assert "uv run python -m cli.model pull whisper-test" in err_text
    assert "data/models/faster-whisper-non-existent-xyz" in err_text


def test_xasr_missing_paths_raises():
    """当 XASR 既未配置 model_name 也未配置 tokens_path 时，实例化必须直接报错。"""
    cfg_data = {
        "engine": "xasr",
        "load": {},
    }
    cfg = EngineConfig("xasr-test", cfg_data)
    with pytest.raises(RuntimeError) as exc_info:
        XASREngine(cfg)

    err_text = str(exc_info.value)
    assert "未配置完整的模型路径" in err_text
    assert "tokens_path" in err_text
    assert "sherpa-onnx" in err_text


def test_xasr_nonexistent_model_raises():
    """当 XASR 配置的 model_name 对应本地文件不存在时，实例化时必须报错并提示 cli.model pull。"""
    cfg_data = {
        "engine": "xasr",
        "load": {
            "model_name": "CustomOrg/non-existent-xasr-xyz",
        },
    }
    cfg = EngineConfig("xasr-test", cfg_data)
    with pytest.raises(RuntimeError) as exc_info:
        XASREngine(cfg)

    err_text = str(exc_info.value)
    assert "模型文件不存在" in err_text
    assert "data/models/non-existent-xasr-xyz/tokens.txt" in err_text
    assert "uv run python -m cli.model pull xasr-test" in err_text


def test_qwen_nonexistent_model_raises():
    """当 Qwen 推导的本地目录不存在时，实例化时应立即报错。"""
    cfg_data = {
        "engine": "qwen",
        "load": {
            "model_name": "Qwen/Qwen3-ASR-NonExistent-99B",
        },
    }
    cfg = EngineConfig("qwen-test", cfg_data)
    with pytest.raises(RuntimeError) as exc_info:
        QwenEngine(cfg)

    err_text = str(exc_info.value)
    assert "配置的模型路径不存在" in err_text
    assert "uv run python -m cli.model pull qwen-test" in err_text
    assert "data/models/Qwen3-ASR-NonExistent-99B" in err_text


def test_qwen_nonexistent_forced_aligner_path_raises(tmp_path):
    """当 Qwen 主模型存在，但 forced_aligner_name 对应本地目录不存在时，必须报错并给出下载指引。"""
    cfg_data = {
        "engine": "qwen",
        "load": {
            "model_name": "Qwen/Qwen3-ASR-1.7B",
            "model_path": str(tmp_path),
            "forced_aligner_name": "Qwen/Qwen3-ForcedAligner-NonExistent",
        },
    }
    cfg = EngineConfig("qwen-test", cfg_data)
    with pytest.raises(RuntimeError) as exc_info:
        QwenEngine(cfg)

    err_text = str(exc_info.value)
    assert "ForcedAligner 对齐模型路径不存在" in err_text
    assert "uv run python -m cli.model pull qwen-test --include-aligner" in err_text
    assert "data/models/Qwen3-ForcedAligner-NonExistent" in err_text


def test_funasr_nonexistent_model_raises():
    """当 FunASR 推导的本地模型目录不存在时，实例化时应立即报错并提示 cli.model pull。"""
    cfg_data = {
        "engine": "funasr",
        "load": {
            "model_name": "iic/NonExistentFunASRModel",
        },
    }
    cfg = EngineConfig("funasr-test", cfg_data)
    with pytest.raises(RuntimeError) as exc_info:
        FunASREngine(cfg)

    err_text = str(exc_info.value)
    assert "配置的模型路径不存在" in err_text
    assert "uv run python -m cli.model pull funasr-test" in err_text
    assert "data/models/NonExistentFunASRModel" in err_text


def test_whisper_valid_local_model_path_passes_validation(tmp_path):
    """当 faster-whisper 的本地目录存在时，通过路径校验并调用 WhisperModel。"""
    cfg_data = {
        "engine": "faster-whisper",
        "load": {
            "model_name": "Systran/faster-whisper-medium",
            "model_path": str(tmp_path),
            "device": "cpu",
            "compute_type": "int8",
        },
    }
    cfg = EngineConfig("whisper-local", cfg_data)
    with patch("server.engines.whisper_engine.WhisperModel", return_value=MagicMock()) as mock_cls:
        engine = WhisperEngine(cfg)
        assert engine.model is not None
        mock_cls.assert_called_once()
