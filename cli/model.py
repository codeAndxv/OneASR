"""OneASR 模型下载、状态查询与完整性校验 CLI 工具。

用法示例:
    # 1. 查看所有模型状态（启用状态、本地路径、就绪状态、占用空间）
    uv run python -m cli.model list

    # 2. 一键下载 config.yaml 中所有已启用 (enable: true) 且本地缺失的模型
    uv run python -m cli.model pull

    # 3. 下载指定的一个或多个 Provider 模型（无视 enable 状态）
    uv run python -m cli.model pull qwen
    uv run python -m cli.model pull xasr faster-whisper

    # 4. 下载 config.yaml 中配置的全部本地模型
    uv run python -m cli.model pull --all

    # 5. 指定下载源 / 强制重下 / 连带下载 Qwen ForcedAligner
    uv run python -m cli.model pull qwen --source modelscope --include-aligner
    uv run python -m cli.model pull faster-whisper --source hf-mirror --force

    # 6. 离线校验已启用模型的文件完整性（CI / Docker 启动前检查）
    uv run python -m cli.model check
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

# 确保直接运行 `python cli/model.py` 时也能正常导入 `server.*`
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.core.config import (  # noqa: E402
    WHISPER_SHORTHAND_MAP,
    AppConfig,
    EngineConfig,
    infer_whisper_repo_id,
)

CLOUD_ENGINES = {"openai", "mimo"}


@dataclass
class ModelArtifactSpec:
    """单个模型权重的下载与校验规格描述。"""

    provider_name: str
    engine_name: str
    label: str  # "main" 或 "forced_aligner"
    enable: bool
    local_dir: Path
    hf_repo_id: str
    ms_repo_id: str
    subdir_in_repo: str | None = None
    required_files: list[str] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        if self.label == "main":
            return self.provider_name
        return f"{self.provider_name} ({self.label})"

    @property
    def relative_local_dir(self) -> str:
        try:
            return str(self.local_dir.relative_to(PROJECT_ROOT))
        except ValueError:
            return str(self.local_dir)


def _match_pattern_group(directory: Path, pattern_group: str) -> list[Path]:
    """检查目录中是否存在匹配模式组（支持 `a|b` 或通配符 `*.onnx`）的非空文件。"""
    matched: list[Path] = []
    for pat in pattern_group.split("|"):
        pat = pat.strip()
        if not pat:
            continue
        for p in directory.glob(pat):
            if p.is_file() and p.stat().st_size > 0:
                matched.append(p)
    return matched


def verify_model_dir(
    engine_name: str,
    local_dir: Path | None,
    required_files: list[str] | None = None,
) -> tuple[bool, list[str]]:
    """校验本地模型目录是否完整有效（防止空目录或中断残缺文件误判为已就绪）。

    Returns:
        (is_valid, missing_reasons)
    """
    if local_dir is None or not local_dir.exists():
        return False, ["目录不存在"]
    if not local_dir.is_dir():
        return False, ["路径不是目录"]

    missing: list[str] = []

    # 1. 按引擎默认核心文件规则填充
    if required_files is None:
        eng = (engine_name or "").lower()
        if eng == "xasr":
            required_files = [
                "tokens.txt",
                "encoder*.onnx",
                "decoder*.onnx",
                "joiner*.onnx",
            ]
        elif eng in ("faster-whisper", "whisper"):
            required_files = [
                "config.json",
                "model.bin",
            ]
        elif eng == "qwen":
            required_files = [
                "config.json",
                "*.safetensors|*.bin",
            ]
        elif eng == "funasr":
            required_files = [
                "config.yaml|configuration.json",
                "model.pt|*.pb|*.onnx",
            ]
        elif eng == "firered":
            required_files = [
                "tokens.txt",
                "encoder*.onnx",
                "decoder*.onnx",
            ]
        else:
            required_files = []

    for req in required_files:
        if not _match_pattern_group(local_dir, req):
            missing.append(f"缺少核心文件: {req}")

    # 2. 针对包含 model.safetensors.index.json 的分片大模型（如 Qwen3-ASR-1.7B），校验所有分片完整性
    index_file = local_dir / "model.safetensors.index.json"
    if index_file.is_file():
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                idx_data = json.load(f)
            weight_map = idx_data.get("weight_map", {})
            shard_files = sorted(set(weight_map.values()))
            for shard_name in shard_files:
                shard_path = local_dir / shard_name
                if not shard_path.is_file() or shard_path.stat().st_size == 0:
                    missing.append(f"缺少权重分片: {shard_name}")
        except Exception as e:
            missing.append(f"索引文件损坏 (model.safetensors.index.json): {e}")

    # 3. 兜底检查目录是否完全为空
    if not required_files:
        has_any_file = any(p.is_file() and p.stat().st_size > 0 for p in local_dir.rglob("*"))
        if not has_any_file:
            missing.append("目录为空")

    return len(missing) == 0, missing


def get_dir_size_str(directory: Path) -> str:
    """计算目录中所有文件的总大小并格式化为人类可读字符串。"""
    if not directory.exists() or not directory.is_dir():
        return "-"
    total_bytes = 0
    for p in directory.rglob("*"):
        if p.is_file() and not p.name.startswith("."):
            try:
                total_bytes += p.stat().st_size
            except OSError:
                pass
    if total_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(total_bytes)
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            return f"{size:.2f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024.0
    return f"{total_bytes} B"


def resolve_provider_specs(
    cfg: EngineConfig,
    include_aligner: bool = False,
) -> list[ModelArtifactSpec]:
    """根据 config.yaml 中的单个 Provider 配置解析出对应的模型下载规格列表。"""
    eng = (cfg.engine_name or cfg.name).lower()
    if cfg.type == "cloud" or getattr(cfg, "is_cloud", False) or eng in CLOUD_ENGINES:
        return []

    specs: list[ModelArtifactSpec] = []

    if eng == "xasr":
        # 从 tokens_path 或 encoder_path 推断本地目标目录
        first_file_str = cfg.tokens_path or cfg.encoder_path or cfg.decoder_path or cfg.joiner_path
        if first_file_str:
            resolved_file = cfg.resolve_path(first_file_str)
            local_dir = resolved_file.parent if resolved_file else PROJECT_ROOT / "data/models/chunk-160ms-model"
        elif cfg.model_path:
            local_dir = cfg.resolve_path(cfg.model_path) or PROJECT_ROOT / "data/models/chunk-160ms-model"
        else:
            local_dir = PROJECT_ROOT / "data/models/chunk-160ms-model"

        chunk_dir_name = local_dir.name if local_dir.name.startswith("chunk-") else "chunk-160ms-model"
        req_files = []
        for path_attr in (cfg.tokens_path, cfg.encoder_path, cfg.decoder_path, cfg.joiner_path):
            if path_attr:
                req_files.append(Path(path_attr).name)
        if not req_files:
            req_files = ["tokens.txt", "encoder*.onnx", "decoder*.onnx", "joiner*.onnx"]

        specs.append(
            ModelArtifactSpec(
                provider_name=cfg.name,
                engine_name="xasr",
                label="main",
                enable=cfg.enable,
                local_dir=local_dir,
                hf_repo_id="GilgameshWind/X-ASR-zh-en",
                ms_repo_id="Gilgamesh-J/X-ASR-zh-en",
                subdir_in_repo=f"deployment/models/{chunk_dir_name}",
                required_files=req_files,
            )
        )

    elif eng in ("whisper", "faster-whisper"):
        repo_id = infer_whisper_repo_id(cfg.model_name)
        default_dir_name = repo_id.split("/")[-1]
        local_dir = (
            cfg.resolve_path(cfg.model_path)
            if cfg.model_path
            else PROJECT_ROOT / "data/models" / default_dir_name
        )
        specs.append(
            ModelArtifactSpec(
                provider_name=cfg.name,
                engine_name="whisper",
                label="main",
                enable=cfg.enable,
                local_dir=local_dir,
                hf_repo_id=repo_id,
                ms_repo_id=repo_id,
                required_files=["config.json", "model.bin"],
            )
        )

    elif eng == "qwen":
        repo_id = (cfg.model_name or "Qwen/Qwen3-ASR-1.7B").strip()
        if "/" not in repo_id:
            repo_id = f"Qwen/{repo_id}"
        default_dir_name = repo_id.split("/")[-1]
        local_dir = (
            cfg.resolve_path(cfg.model_path)
            if cfg.model_path
            else PROJECT_ROOT / "data/models" / default_dir_name
        )
        specs.append(
            ModelArtifactSpec(
                provider_name=cfg.name,
                engine_name="qwen",
                label="main",
                enable=cfg.enable,
                local_dir=local_dir,
                hf_repo_id=repo_id,
                ms_repo_id=repo_id,
                required_files=["config.json", "*.safetensors|*.bin"],
            )
        )

        # 如果配置了 forced_aligner_path 或显式开启 --include-aligner，则连带解析 ForcedAligner
        if cfg.forced_aligner_path or cfg.forced_aligner_name or include_aligner:
            fa_repo = (cfg.forced_aligner_name or "Qwen/Qwen3-ForcedAligner-0.6B").strip()
            if "/" not in fa_repo:
                fa_repo = f"Qwen/{fa_repo}"
            fa_dir_name = fa_repo.split("/")[-1]
            fa_local_dir = (
                cfg.resolve_path(cfg.forced_aligner_path)
                if cfg.forced_aligner_path
                else PROJECT_ROOT / "data/models" / fa_dir_name
            )
            specs.append(
                ModelArtifactSpec(
                    provider_name=cfg.name,
                    engine_name="qwen",
                    label="forced_aligner",
                    enable=cfg.enable,
                    local_dir=fa_local_dir,
                    hf_repo_id=fa_repo,
                    ms_repo_id=fa_repo,
                    required_files=["config.json", "*.safetensors|*.bin"],
                )
            )

    elif eng == "funasr":
        raw_main = (cfg.model_name or "iic/SenseVoiceSmall").strip()
        if raw_main in ("SenseVoiceSmall", "iic/SenseVoiceSmall", "FunAudioLLM/SenseVoiceSmall"):
            ms_repo = "iic/SenseVoiceSmall"
            hf_repo = "FunAudioLLM/SenseVoiceSmall"
        elif raw_main == "paraformer-zh" or "paraformer" in raw_main:
            ms_repo = (
                "iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
                if "/" not in raw_main
                else raw_main
            )
            hf_repo = "funasr/paraformer-zh"
        else:
            ms_repo = raw_main
            hf_repo = raw_main

        default_dir_name = ms_repo.split("/")[-1]
        local_dir = (
            cfg.resolve_path(cfg.model_path)
            if cfg.model_path
            else PROJECT_ROOT / "data/models" / default_dir_name
        )
        specs.append(
            ModelArtifactSpec(
                provider_name=cfg.name,
                engine_name="funasr",
                label="main",
                enable=cfg.enable,
                local_dir=local_dir,
                hf_repo_id=hf_repo,
                ms_repo_id=ms_repo,
                required_files=["config.yaml|configuration.json", "model.pt|*.pb|*.onnx"],
            )
        )

        # 解析附属 VAD 模型（如配置了 vad_model 或 vad_model_path）
        vad_name = getattr(cfg, "vad_model", "") or ""
        vad_path = getattr(cfg, "vad_model_path", "") or ""
        if vad_name or vad_path:
            if vad_name in ("", "fsmn-vad", "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"):
                vad_ms_repo = "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
                vad_hf_repo = "funasr/fsmn-vad"
            else:
                vad_ms_repo = vad_name.strip()
                vad_hf_repo = vad_ms_repo
            vad_dir_name = vad_ms_repo.split("/")[-1]
            vad_local_dir = (
                cfg.resolve_path(vad_path)
                if vad_path
                else PROJECT_ROOT / "data/models" / vad_dir_name
            )
            specs.append(
                ModelArtifactSpec(
                    provider_name=cfg.name,
                    engine_name="funasr",
                    label="vad_model",
                    enable=cfg.enable,
                    local_dir=vad_local_dir,
                    hf_repo_id=vad_hf_repo,
                    ms_repo_id=vad_ms_repo,
                    required_files=["config.yaml|configuration.json", "model.pt|*.pb|*.onnx"],
                )
            )

        # 解析附属标点恢复模型（如配置了 punc_model 或 punc_model_path）
        punc_name = getattr(cfg, "punc_model", "") or ""
        punc_path = getattr(cfg, "punc_model_path", "") or ""
        if punc_name or punc_path:
            if punc_name in ("", "ct-punc", "iic/punc_ct-transformer_cn-en-common-vocab471067-large"):
                punc_ms_repo = "iic/punc_ct-transformer_cn-en-common-vocab471067-large"
                punc_hf_repo = "funasr/ct-punc"
            else:
                punc_ms_repo = punc_name.strip()
                punc_hf_repo = punc_ms_repo
            punc_dir_name = punc_ms_repo.split("/")[-1]
            punc_local_dir = (
                cfg.resolve_path(punc_path)
                if punc_path
                else PROJECT_ROOT / "data/models" / punc_dir_name
            )
            specs.append(
                ModelArtifactSpec(
                    provider_name=cfg.name,
                    engine_name="funasr",
                    label="punc_model",
                    enable=cfg.enable,
                    local_dir=punc_local_dir,
                    hf_repo_id=punc_hf_repo,
                    ms_repo_id=punc_ms_repo,
                    required_files=["config.yaml|configuration.json", "model.pt|*.pb|*.onnx"],
                )
            )

    elif eng == "firered":
        raw_name = (cfg.model_name or "").strip()
        if "/" in raw_name:
            repo_id = raw_name
        else:
            repo_id = "csukuangfj/sherpa-onnx-fire-red-asr-large-zh_en-2025-02-16"
        default_dir_name = repo_id.split("/")[-1]
        local_dir = (
            cfg.resolve_path(cfg.model_path)
            if cfg.model_path
            else PROJECT_ROOT / "data/models" / default_dir_name
        )
        specs.append(
            ModelArtifactSpec(
                provider_name=cfg.name,
                engine_name="firered",
                label="main",
                enable=cfg.enable,
                local_dir=local_dir,
                hf_repo_id=repo_id,
                ms_repo_id=repo_id,
                required_files=["tokens.txt", "encoder*.onnx", "decoder*.onnx"],
            )
        )

    return specs


def _ms_snapshot_download(
    model_id: str,
    local_dir: str,
    allow_patterns: list[str] | None = None,
) -> str:
    """调用 ModelScope SDK 下载模型。"""
    from modelscope import snapshot_download as ms_download

    return ms_download(
        model_id=model_id,
        local_dir=local_dir,
        allow_patterns=allow_patterns,
    )


def _hf_snapshot_download(
    repo_id: str,
    local_dir: str,
    allow_patterns: list[str] | None = None,
    endpoint: str | None = None,
) -> str:
    """调用 HuggingFace Hub SDK 下载模型。"""
    from huggingface_hub import snapshot_download as hf_download

    return hf_download(
        repo_id=repo_id,
        local_dir=local_dir,
        allow_patterns=allow_patterns,
        endpoint=endpoint,
    )


def _download_from_single_source(
    spec: ModelArtifactSpec,
    source: str,
) -> None:
    """使用指定源 (modelscope / huggingface / hf-mirror) 下载模型并完成子目录扁平化整理。"""
    target_dir = spec.local_dir
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    # 如果模型文件位于仓库子目录（例如 xasr 的 deployment/models/chunk-160ms-model），先下载到临时目录再提取
    if spec.subdir_in_repo:
        staging_dir = target_dir.parent / f".staging_{target_dir.name}"
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        staging_dir.mkdir(parents=True, exist_ok=True)
        allow_patterns = [f"{spec.subdir_in_repo.strip('/')}/*"]
        download_dest = staging_dir
    else:
        staging_dir = None
        allow_patterns = None
        download_dest = target_dir

    try:
        if source == "modelscope":
            print(f"  -> [ModelScope] 正在拉取 {spec.ms_repo_id} ...")
            _ms_snapshot_download(
                model_id=spec.ms_repo_id,
                local_dir=str(download_dest),
                allow_patterns=allow_patterns,
            )
        elif source in ("huggingface", "hf-mirror"):
            endpoint = "https://hf-mirror.com" if source == "hf-mirror" else os.environ.get("HF_ENDPOINT")
            label_src = "HF-Mirror" if source == "hf-mirror" else "HuggingFace"
            print(f"  -> [{label_src}] 正在拉取 {spec.hf_repo_id} ...")
            _hf_snapshot_download(
                repo_id=spec.hf_repo_id,
                local_dir=str(download_dest),
                allow_patterns=allow_patterns,
                endpoint=endpoint,
            )
        else:
            raise ValueError(f"不支持的下载源: {source}")

        # 若为子目录模式，将子目录内的模型文件扁平化移动到最终 target_dir
        if staging_dir is not None and spec.subdir_in_repo:
            extracted_subdir = staging_dir / spec.subdir_in_repo.strip("/")
            if not extracted_subdir.exists():
                raise RuntimeError(f"下载后未找到预期子目录: {spec.subdir_in_repo}")
            target_dir.mkdir(parents=True, exist_ok=True)
            for item in extracted_subdir.iterdir():
                dest_item = target_dir / item.name
                if dest_item.exists():
                    if dest_item.is_dir():
                        shutil.rmtree(dest_item)
                    else:
                        dest_item.unlink()
                shutil.move(str(item), str(dest_item))
    finally:
        if staging_dir is not None and staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)


def download_artifact(
    spec: ModelArtifactSpec,
    source: str = "auto",
    force: bool = False,
) -> bool:
    """下载单个模型权重，支持多源自动降级与下载后完整性校验。"""
    is_valid, missing_reasons = verify_model_dir(
        spec.engine_name, spec.local_dir, spec.required_files
    )
    if is_valid and not force:
        size_str = get_dir_size_str(spec.local_dir)
        print(f"[SKIP] {spec.display_name} 已就绪 ({spec.relative_local_dir}, {size_str})")
        return True

    if not is_valid and spec.local_dir.exists() and not force:
        print(
            f"[INFO] {spec.display_name} 本地目录存在但文件不完整 ({'; '.join(missing_reasons)})，将断点续传补齐..."
        )

    if source == "auto":
        candidate_sources = ["modelscope", "hf-mirror", "huggingface"]
    else:
        candidate_sources = [source]

    print(f"[PULL] 开始下载 {spec.display_name} -> {spec.relative_local_dir}")
    last_error: Exception | None = None

    for src in candidate_sources:
        try:
            _download_from_single_source(spec, src)
            ok, reasons = verify_model_dir(
                spec.engine_name, spec.local_dir, spec.required_files
            )
            if not ok:
                raise RuntimeError(f"下载完成但完整性校验未通过: {'; '.join(reasons)}")

            size_str = get_dir_size_str(spec.local_dir)
            print(f"[DONE] {spec.display_name} 下载并校验成功！({spec.relative_local_dir}, {size_str})")
            return True
        except Exception as e:
            last_error = e
            print(f"  [WARN] 从数据源 [{src}] 下载 {spec.display_name} 失败: {e}")
            if src != candidate_sources[-1]:
                print("  [INFO] 正在自动切换备用下载源重试...")

    print(f"[FAIL] {spec.display_name} 下载失败: {last_error}", file=sys.stderr)
    return False


def collect_all_specs(
    app_cfg: AppConfig,
    include_aligner: bool = False,
) -> list[ModelArtifactSpec]:
    """收集 config.yaml 中所有本地 Provider 的模型规格。"""
    all_specs: list[ModelArtifactSpec] = []
    local_dict = getattr(app_cfg, "local_models", app_cfg.providers)
    for prov_cfg in local_dict.values():
        all_specs.extend(resolve_provider_specs(prov_cfg, include_aligner=include_aligner))
    return all_specs


def cmd_list(args: argparse.Namespace) -> int:
    """列出 config.yaml 中所有本地模型的状态与磁盘占用。"""
    app_cfg = AppConfig(args.config)
    specs = collect_all_specs(app_cfg, include_aligner=True)

    print("=" * 125)
    print(
        f"{'PROVIDER':<22} {'ENGINE':<15} {'ENABLED':<8} {'STATUS':<11} {'SIZE':<10} {'MODEL REPO':<42} {'LOCAL PATH'}"
    )
    print("-" * 125)
    for spec in specs:
        ok, reasons = verify_model_dir(
            spec.engine_name, spec.local_dir, spec.required_files
        )
        if ok:
            status_str = "Ready"
        elif spec.local_dir.exists():
            status_str = "Incomplete"
        else:
            status_str = "Missing"

        enabled_str = "Yes" if spec.enable else "No"
        size_str = get_dir_size_str(spec.local_dir) if ok else "-"
        print(
            f"{spec.display_name:<22} {spec.engine_name:<15} {enabled_str:<8} "
            f"{status_str:<11} {size_str:<10} {spec.ms_repo_id:<42} {spec.relative_local_dir}"
        )
        if not ok and spec.local_dir.exists() and reasons:
            print(f"  └─ 缺失项: {'; '.join(reasons)}")
    print("=" * 125)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """校验模型完整性（默认校验所有 enable=True 的本地模型，或通过 --all 校验全部）。"""
    app_cfg = AppConfig(args.config)
    specs = collect_all_specs(app_cfg, include_aligner=False)

    if args.providers:
        target_names = set(args.providers)
        specs = [s for s in specs if s.provider_name in target_names]
    elif not args.all:
        specs = [s for s in specs if s.enable]

    all_ok = True
    for spec in specs:
        ok, reasons = verify_model_dir(
            spec.engine_name, spec.local_dir, spec.required_files
        )
        if ok:
            print(f"[OK]   {spec.display_name:<20} -> {spec.relative_local_dir}")
        else:
            all_ok = False
            print(
                f"[ERR]  {spec.display_name:<20} -> {spec.relative_local_dir} ({'; '.join(reasons)})",
                file=sys.stderr,
            )

    if not all_ok:
        print(
            "\n提示: 请运行 `uv run python -m cli.model pull` 下载缺失的模型。",
            file=sys.stderr,
        )
        return 1
    return 0


def cmd_pull(args: argparse.Namespace) -> int:
    """根据指定参数下载模型到 config.yaml 配置的目录。"""
    app_cfg = AppConfig(args.config)
    specs = collect_all_specs(app_cfg, include_aligner=args.include_aligner)

    if args.providers:
        available = {
            p for p, c in getattr(app_cfg, "local_models", app_cfg.providers).items()
            if not getattr(c, "is_cloud", False) and c.type != "cloud" and c.engine_name not in CLOUD_ENGINES
        }
        unknown = [p for p in args.providers if p not in available]
        if unknown:
            print(
                f"[ERROR] 未知的本地 Provider: {', '.join(unknown)} (可用本地 Provider: {', '.join(sorted(available))})",
                file=sys.stderr,
            )
            return 1
        target_set = set(args.providers)
        selected_specs = [s for s in specs if s.provider_name in target_set]
    elif args.all:
        selected_specs = specs
    else:
        # 默认仅拉取 config.yaml 中 enable: true 的本地模型
        selected_specs = [s for s in specs if s.enable]

    if not selected_specs:
        print("[INFO] 没有需要下载的已启用本地模型。如需下载未启用的模型，请指定名称或使用 `--all`。")
        return 0

    success_count = 0
    fail_count = 0
    for spec in selected_specs:
        if download_artifact(spec, source=args.source, force=args.force):
            success_count += 1
        else:
            fail_count += 1

    print("-" * 60)
    print(f"模型拉取汇总: 成功 {success_count} 个, 失败 {fail_count} 个")
    return 0 if fail_count == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m cli.model",
        description="OneASR 本地模型下载、状态查询与完整性校验工具",
    )
    parser.add_argument(
        "-c",
        "--config",
        default=None,
        help="指定 config.yaml 路径（默认使用项目根目录 config.yaml）",
    )

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # 1. list 子命令
    subparsers.add_parser("list", help="列出所有本地模型的状态与磁盘占用")

    # 2. pull 子命令
    pull_parser = subparsers.add_parser(
        "pull",
        help="下载模型到 config.yaml 配置的目录（默认下载所有 enable: true 的模型）",
    )
    pull_parser.add_argument(
        "providers",
        nargs="*",
        help="指定要下载的 Provider 名称（如 xasr faster-whisper qwen），留空则下载所有已启用模型",
    )
    pull_parser.add_argument(
        "--all",
        action="store_true",
        help="下载 config.yaml 中配置的全部本地模型（包含 enable: false 的模型）",
    )
    pull_parser.add_argument(
        "--source",
        choices=["auto", "modelscope", "huggingface", "hf-mirror"],
        default="auto",
        help="指定下载源（默认 auto: 优先 ModelScope，失败自动切换 HF-Mirror / HuggingFace）",
    )
    pull_parser.add_argument(
        "--force",
        action="store_true",
        help="即使本地模型已就绪也强制重新下载校验",
    )
    pull_parser.add_argument(
        "--include-aligner",
        action="store_true",
        help="下载 Qwen 模型时同时拉取 Qwen3-ForcedAligner-0.6B 时间戳对齐模型",
    )

    # 3. check 子命令
    check_parser = subparsers.add_parser(
        "check",
        help="离线校验本地模型文件是否完整（默认检查所有 enable: true 的模型）",
    )
    check_parser.add_argument(
        "providers",
        nargs="*",
        help="指定要校验的 Provider 名称",
    )
    check_parser.add_argument(
        "--all",
        action="store_true",
        help="校验全部配置的本地模型（包含 enable: false 的模型）",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.subcommand == "list":
        return cmd_list(args)
    if args.subcommand == "pull":
        return cmd_pull(args)
    if args.subcommand == "check":
        return cmd_check(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
