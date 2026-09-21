"""测试模型路径校验与错误下载提示。"""

import pytest

from app.core.config import EngineConfig, PROJECT_ROOT
from app.engines.whisper_engine import WhisperEngine
from app.engines.xasr_engine import XASREngine
from app.engines.qwen_engine import QwenEngine


def test_engine_config_paths():
    """测试 EngineConfig 对各类 path 字段的解析。"""
    cfg_data = {
        "engine": "faster-whisper",
        "load": {
            "model_name": "medium",
            "model_path": "models/medium",
        },
    }
    cfg = EngineConfig("faster-whisper", cfg_data)
    assert cfg.model_path == "models/medium"
    assert cfg.resolve_path(cfg.model_path) == PROJECT_ROOT / "models/medium"


def test_whisper_nonexistent_model_path_raises():
    """当 faster-whisper 的 model_path 不存在时，必须抛出 RuntimeError 并包含下载命令。"""
    cfg_data = {
        "engine": "faster-whisper",
        "load": {
            "model_name": "medium",
            "model_path": "models/non_existent_folder_xyz",
        },
    }
    cfg = EngineConfig("whisper-test", cfg_data)
    with pytest.raises(RuntimeError) as exc_info:
        WhisperEngine(cfg)

    err_text = str(exc_info.value)
    assert "配置的模型路径不存在" in err_text
    assert "hf download Systran/faster-whisper-medium --local-dir models/non_existent_folder_xyz" in err_text
    assert "models/non_existent_folder_xyz" in err_text


def test_xasr_missing_paths_raises():
    """当 XASR 缺少必要的 path 配置时，实例化时必须直接报错并包含 sherpa-onnx 下载指引。"""
    cfg_data = {
        "engine": "xasr",
        "load": {
            "model_name": "xasr-zh-en",
            # 未配置 tokens_path, encoder_path, decoder_path, joiner_path
        },
    }
    cfg = EngineConfig("xasr-test", cfg_data)
    with pytest.raises(RuntimeError) as exc_info:
        XASREngine(cfg)

    err_text = str(exc_info.value)
    assert "未配置完整的模型路径" in err_text
    assert "tokens_path" in err_text
    assert "sherpa-onnx" in err_text


def test_xasr_nonexistent_file_path_raises():
    """当 XASR 配置了路径但文件不存在时，实例化时必须报错。"""
    cfg_data = {
        "engine": "xasr",
        "load": {
            "tokens_path": "models/fake/tokens.txt",
            "encoder_path": "models/fake/encoder.onnx",
            "decoder_path": "models/fake/decoder.onnx",
            "joiner_path": "models/fake/joiner.onnx",
        },
    }
    cfg = EngineConfig("xasr-test", cfg_data)
    with pytest.raises(RuntimeError) as exc_info:
        XASREngine(cfg)

    err_text = str(exc_info.value)
    assert "模型文件不存在" in err_text
    assert "models/fake/tokens.txt" in err_text


def test_qwen_nonexistent_model_path_raises():
    """当 Qwen 配置了不存在的 model_path 时，实例化时应立即报错。"""
    cfg_data = {
        "engine": "qwen",
        "load": {
            "model_name": "Qwen/Qwen3-ASR-1.7B",
            "model_path": "models/non_existent_qwen_path",
        },
    }
    cfg = EngineConfig("qwen-test", cfg_data)
    with pytest.raises(RuntimeError) as exc_info:
        QwenEngine(cfg)

    err_text = str(exc_info.value)
    assert "配置的模型路径不存在" in err_text
    assert "hf download Qwen/Qwen3-ASR-1.7B" in err_text


def test_qwen_nonexistent_forced_aligner_path_raises(tmp_path):
    """当 Qwen 的主模型存在（或使用在线名称），但 forced_aligner_path 不存在时，必须报错并给出下载指引。"""
    cfg_data = {
        "engine": "qwen",
        "load": {
            "model_name": "Qwen/Qwen3-ASR-1.7B",
            "model_path": str(tmp_path),  # 模拟主模型路径存在
            "forced_aligner_name": "Qwen/Qwen3-ForcedAligner-0.6B",
            "forced_aligner_path": "models/non_existent_aligner_path",
        },
    }
    cfg = EngineConfig("qwen-test", cfg_data)
    with pytest.raises(RuntimeError) as exc_info:
        QwenEngine(cfg)

    err_text = str(exc_info.value)
    assert "ForcedAligner 对齐模型路径不存在" in err_text
    assert "hf download Qwen/Qwen3-ForcedAligner-0.6B" in err_text
    assert "models/non_existent_aligner_path" in err_text


def test_whisper_valid_local_model_loads():
    """当 faster-whisper 的 model_path 存在（models/medium）时，可正常实例化。"""
    local_path = PROJECT_ROOT / "models/medium"
    if not local_path.exists():
        pytest.skip("本地 models/medium 不存在，跳过本地模型加载验证")

    cfg_data = {
        "engine": "faster-whisper",
        "load": {
            "model_name": "medium",
            "model_path": "models/medium",
            "device": "cpu",
            "compute_type": "int8",
        },
    }
    cfg = EngineConfig("whisper-local", cfg_data)
    engine = WhisperEngine(cfg)
    assert engine.model is not None

