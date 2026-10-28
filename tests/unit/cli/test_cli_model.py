"""OneASR CLI 模型下载与校验工具 (cli/model.py) 单元测试。"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from cli.model import (
    ModelArtifactSpec,
    download_artifact,
    infer_whisper_repo_id,
    main,
    resolve_provider_specs,
    verify_model_dir,
)
from server.core.config import EngineConfig

pytestmark = pytest.mark.unit


def test_infer_whisper_repo_id():
    assert infer_whisper_repo_id("medium") == "Systran/faster-whisper-medium"
    assert infer_whisper_repo_id("large-v3") == "Systran/faster-whisper-large-v3"
    assert infer_whisper_repo_id("turbo") == "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
    assert infer_whisper_repo_id("faster-whisper-small") == "Systran/faster-whisper-small"
    assert infer_whisper_repo_id("CustomOrg/my-whisper") == "CustomOrg/my-whisper"


def test_verify_model_dir_detects_missing_and_empty_dirs(tmp_path: Path):
    # 1. 不存在的目录
    ok, reasons = verify_model_dir("faster-whisper", tmp_path / "not_exist")
    assert ok is False
    assert "目录不存在" in reasons[0]

    # 2. 半截空目录（仅有 config.json，缺少 model.bin）
    incomplete_dir = tmp_path / "whisper_incomplete"
    incomplete_dir.mkdir()
    (incomplete_dir / "config.json").write_text("{}", encoding="utf-8")
    ok, reasons = verify_model_dir("faster-whisper", incomplete_dir)
    assert ok is False
    assert any("model.bin" in r for r in reasons)

    # 3. 补齐非空 model.bin 后通过校验
    (incomplete_dir / "model.bin").write_bytes(b"dummy-weights")
    ok, reasons = verify_model_dir("faster-whisper", incomplete_dir)
    assert ok is True
    assert reasons == []


def test_verify_model_dir_checks_safetensors_shards(tmp_path: Path):
    """当存在 model.safetensors.index.json 时，必须检查所有分片文件是否完整下载。"""
    qwen_dir = tmp_path / "Qwen3-ASR-1.7B"
    qwen_dir.mkdir()
    (qwen_dir / "config.json").write_text("{}", encoding="utf-8")

    # 索引声明了 2 个分片，但本地只有第 1 个分片（模拟下载中断）
    index_data = {
        "weight_map": {
            "layer.0.weight": "model-00001-of-00002.safetensors",
            "layer.1.weight": "model-00002-of-00002.safetensors",
        }
    }
    (qwen_dir / "model.safetensors.index.json").write_text(
        json.dumps(index_data), encoding="utf-8"
    )
    (qwen_dir / "model-00001-of-00002.safetensors").write_bytes(b"shard1")

    ok, reasons = verify_model_dir("qwen", qwen_dir)
    assert ok is False
    assert any("model-00002-of-00002.safetensors" in r for r in reasons)

    # 补齐第 2 个分片后校验通过
    (qwen_dir / "model-00002-of-00002.safetensors").write_bytes(b"shard2")
    ok, reasons = verify_model_dir("qwen", qwen_dir)
    assert ok is True
    assert reasons == []


def test_resolve_provider_specs_for_all_engines(tmp_path: Path):
    # 1. X-ASR
    xasr_cfg = EngineConfig(
        "xasr",
        {
            "enable": True,
            "engine": "xasr",
            "load": {
                "tokens_path": str(tmp_path / "chunk-160ms-model/tokens.txt"),
                "encoder_path": str(tmp_path / "chunk-160ms-model/encoder-160ms.onnx"),
                "decoder_path": str(tmp_path / "chunk-160ms-model/decoder-160ms.onnx"),
                "joiner_path": str(tmp_path / "chunk-160ms-model/joiner-160ms.onnx"),
            },
        },
    )
    xasr_specs = resolve_provider_specs(xasr_cfg)
    assert len(xasr_specs) == 1
    assert xasr_specs[0].hf_repo_id == "GilgameshWind/X-ASR-zh-en"
    assert xasr_specs[0].ms_repo_id == "Gilgamesh-J/X-ASR-zh-en"
    assert xasr_specs[0].subdir_in_repo == "deployment/models/chunk-160ms-model"
    assert xasr_specs[0].local_dir == tmp_path / "chunk-160ms-model"

    # 2. Qwen (带 include_aligner)
    qwen_cfg = EngineConfig(
        "qwen",
        {
            "enable": False,
            "engine": "qwen",
            "load": {
                "model_name": "Qwen/Qwen3-ASR-1.7B",
                "model_path": str(tmp_path / "Qwen3-ASR-1.7B"),
            },
        },
    )
    assert len(resolve_provider_specs(qwen_cfg, include_aligner=False)) == 1
    qwen_with_fa = resolve_provider_specs(qwen_cfg, include_aligner=True)
    assert len(qwen_with_fa) == 2
    assert qwen_with_fa[1].label == "forced_aligner"
    assert qwen_with_fa[1].hf_repo_id == "Qwen/Qwen3-ForcedAligner-0.6B"

    # 3. FunASR (仅配置 model_name + vad_model，自动推导 data/models/ 路径)
    funasr_cfg = EngineConfig(
        "funasr",
        {
            "enable": False,
            "engine": "funasr",
            "load": {
                "model_name": "iic/SenseVoiceSmall",
                "vad_model": "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
            },
        },
    )
    funasr_specs = resolve_provider_specs(funasr_cfg)
    assert len(funasr_specs) == 2
    assert funasr_specs[0].label == "main"
    assert funasr_specs[0].ms_repo_id == "iic/SenseVoiceSmall"
    assert funasr_specs[0].hf_repo_id == "FunAudioLLM/SenseVoiceSmall"
    assert "SenseVoiceSmall" in funasr_specs[0].relative_local_dir
    assert funasr_specs[1].label == "vad_model"
    assert funasr_specs[1].ms_repo_id == "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
    assert "speech_fsmn_vad_zh-cn-16k-common-pytorch" in funasr_specs[1].relative_local_dir

    # 4. Cloud 引擎不生成本地下载规格
    cloud_cfg = EngineConfig("openai", {"engine": "openai", "type": "cloud"})
    assert resolve_provider_specs(cloud_cfg) == []


def test_download_artifact_flattens_xasr_subdir_and_cleans_staging(
    tmp_path: Path, monkeypatch
):
    """测试 X-ASR 子目录提取：从 deployment/models/chunk-160ms-model 扁平化移动到目标目录并清理临时目录。"""
    target_dir = tmp_path / "chunk-160ms-model"
    spec = ModelArtifactSpec(
        provider_name="xasr",
        engine_name="xasr",
        label="main",
        enable=True,
        local_dir=target_dir,
        hf_repo_id="GilgameshWind/X-ASR-zh-en",
        ms_repo_id="Gilgamesh-J/X-ASR-zh-en",
        subdir_in_repo="deployment/models/chunk-160ms-model",
        required_files=[
            "tokens.txt",
            "encoder-160ms.onnx",
            "decoder-160ms.onnx",
            "joiner-160ms.onnx",
        ],
    )

    def fake_ms_download(model_id: str, local_dir: str, allow_patterns=None):
        sub = Path(local_dir) / "deployment/models/chunk-160ms-model"
        sub.mkdir(parents=True, exist_ok=True)
        for fname in spec.required_files:
            (sub / fname).write_bytes(b"onnx-content")
        return str(local_dir)

    monkeypatch.setattr("cli.model._ms_snapshot_download", fake_ms_download)

    ok = download_artifact(spec, source="modelscope")
    assert ok is True
    for fname in spec.required_files:
        assert (target_dir / fname).is_file()
    # 确保临时 staging 目录已被清理
    assert not (tmp_path / ".staging_chunk-160ms-model").exists()


def test_download_artifact_auto_fallback_from_modelscope_to_hf(
    tmp_path: Path, monkeypatch
):
    """当 auto 模式下 ModelScope 下载报错时，应自动降级到 HuggingFace 镜像并成功完成。"""
    target_dir = tmp_path / "faster-whisper-medium"
    spec = ModelArtifactSpec(
        provider_name="faster-whisper",
        engine_name="faster-whisper",
        label="main",
        enable=True,
        local_dir=target_dir,
        hf_repo_id="Systran/faster-whisper-medium",
        ms_repo_id="Systran/faster-whisper-medium",
        required_files=["config.json", "model.bin"],
    )

    def failing_ms_download(**kwargs):
        raise ConnectionError("ModelScope network unreachable")

    hf_calls = []

    def succeeding_hf_download(repo_id: str, local_dir: str, allow_patterns=None, endpoint=None):
        hf_calls.append((repo_id, endpoint))
        dest = Path(local_dir)
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "config.json").write_text("{}", encoding="utf-8")
        (dest / "model.bin").write_bytes(b"weights")
        return str(dest)

    monkeypatch.setattr("cli.model._ms_snapshot_download", failing_ms_download)
    monkeypatch.setattr("cli.model._hf_snapshot_download", succeeding_hf_download)

    ok = download_artifact(spec, source="auto")
    assert ok is True
    assert len(hf_calls) == 1
    assert hf_calls[0] == ("Systran/faster-whisper-medium", "https://hf-mirror.com")


def test_cli_list_and_check_commands():
    """验证 CLI list 与 check 命令在现有项目模型上正常执行并返回 0。"""
    assert main(["list"]) == 0
    assert main(["check"]) == 0
