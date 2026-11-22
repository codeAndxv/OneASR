"""Filesystem model discovery and integrity scanner.

Inspects the models directory (~/.oneasr/models and legacy data/models) to detect
which model weights are physically downloaded and ready for inference,
treating the filesystem as the single source of truth.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from server.core.manifest import BUILTIN_MODELS, ModelManifest, WHISPER_LANGUAGES, get_manifest
from server.core.paths import get_models_dir, get_settings_path


@dataclass
class ModelScanResult:
    """Represents the real-time on-disk status of a model."""

    id: str
    name: str
    driver: str
    ms_repo: str
    hf_repo: str
    categories: list[str]
    languages: list[str]
    status: str  # "ready", "downloading", "not_downloaded", "corrupted"
    model_path: Path | None = None
    size_on_disk: int = 0
    size_expected: int = 0
    features: list[str] = field(default_factory=list)
    preload: bool = False
    keep_alive: int = 600
    is_custom: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


def _get_search_paths() -> list[Path]:
    """Return all directories to inspect for models (strictly ~/.oneasr/models or ONEASR_MODELS_DIR)."""
    return [get_models_dir()]


def _calc_dir_size(path: Path) -> int:
    """Calculate the total size in bytes of all files in a directory."""
    if not path.exists():
        return 0
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file(follow_symlinks=False):
                total += entry.stat().st_size
            elif entry.is_dir(follow_symlinks=False):
                total += _calc_dir_size(Path(entry.path))
    except (PermissionError, FileNotFoundError):
        pass
    return total


def find_model_dir(model_id: str, ms_repo: str = "", hf_repo: str = "") -> Path | None:
    """Locate the physical directory of a model across configured search paths."""
    search_dirs = _get_search_paths()
    ms_tail = ms_repo.split("/")[-1] if "/" in ms_repo else ms_repo
    hf_tail = hf_repo.split("/")[-1] if "/" in hf_repo else hf_repo

    candidate_names: list[str] = []

    # 严格模式：Whisper 系列模型严格且仅允许 faster-whisper-xxx 或 faster-distil-whisper-xxx 目录名
    if model_id.startswith("whisper-"):
        short = model_id.replace("whisper-", "")
        candidate_names.append(f"faster-whisper-{short}")
        if "-en" in short:
            dotted = short.replace("-en", ".en")
            candidate_names.append(f"faster-whisper-{dotted}")
        if ms_tail.startswith("faster-whisper-"):
            candidate_names.append(ms_tail)
        if hf_tail.startswith("faster-whisper-"):
            candidate_names.append(hf_tail)
    elif model_id.startswith("distil-whisper-"):
        short = model_id.replace("distil-whisper-", "")
        candidate_names.append(f"faster-distil-whisper-{short}")
        if "-en" in short:
            dotted = short.replace("-en", ".en")
            candidate_names.append(f"faster-distil-whisper-{dotted}")
        if ms_tail.startswith("faster-distil-whisper-"):
            candidate_names.append(ms_tail)
        if hf_tail.startswith("faster-distil-whisper-"):
            candidate_names.append(hf_tail)
    elif model_id.startswith("xasr-zh-en-"):
        chunk = model_id.replace("xasr-zh-en-", "")
        candidate_names.extend([model_id, f"chunk-{chunk}-model"])
    else:
        # 非 Whisper 模型按标准仓库后缀与模型 ID 查找
        for name in (ms_tail, hf_tail, model_id):
            if name:
                candidate_names.append(name)

    # 去重且保持顺序
    seen: set[str] = set()
    deduped_candidates: list[str] = []
    for c in candidate_names:
        if c not in seen:
            seen.add(c)
            deduped_candidates.append(c)

    for base in search_dirs:
        if not base.exists():
            continue
        for name in deduped_candidates:
            target = base / name
            if target.is_dir():
                return target
    return None


def verify_model_integrity(model_path: Path, manifest: ModelManifest | None) -> bool:
    """Verify that all required weights and configs exist in the directory."""
    if not model_path.is_dir():
        return False

    # Check for temporary download lock files
    if (model_path / ".downloading").exists():
        return False

    if manifest and manifest.required_files:
        for fname in manifest.required_files:
            if "*" in fname:
                if not any(model_path.glob(fname)):
                    return False
            else:
                if not (model_path / fname).exists():
                    return False
        return True

    # Generic check: directory must have at least one weight/config file
    has_files = any(
        f.suffix in {".pt", ".bin", ".onnx", ".safetensors", ".yaml", ".json"}
        for f in model_path.iterdir()
        if f.is_file()
    )
    return has_files


def scan_all_models() -> dict[str, ModelScanResult]:
    """Scan search paths and match against the built-in manifest.

    Returns a comprehensive mapping of model_id -> ModelScanResult.
    """
    results: dict[str, ModelScanResult] = {}

    # 1. Process all built-in catalog models
    for model_id, manifest in BUILTIN_MODELS.items():
        found_dir = find_model_dir(model_id, manifest.ms_repo, manifest.hf_repo)
        if found_dir and found_dir.is_dir():
            if (found_dir / ".downloading").exists():
                status = "downloading"
            elif verify_model_integrity(found_dir, manifest):
                status = "ready"
            else:
                status = "corrupted"
            size = _calc_dir_size(found_dir)
        else:
            status = "not_downloaded"
            size = 0
            found_dir = None

        results[model_id] = ModelScanResult(
            id=model_id,
            name=manifest.name,
            driver=manifest.driver,
            ms_repo=manifest.ms_repo,
            hf_repo=manifest.hf_repo,
            categories=manifest.categories,
            languages=manifest.languages,
            status=status,
            model_path=found_dir,
            size_on_disk=size,
            size_expected=manifest.size_bytes,
            features=manifest.features,
            preload=manifest.preload,
            keep_alive=manifest.keep_alive,
            extra=manifest.extra,
        )

    # 2. Load user explicitly registered custom models from settings.json
    settings_file = get_settings_path()
    custom_models_list: list[dict[str, Any]] = []
    if settings_file.is_file():
        try:
            import json
            with open(settings_file, "r", encoding="utf-8") as f:
                s_data = json.load(f)
                if isinstance(s_data, dict):
                    custom_models_list = [
                        c for c in s_data.get("custom_models", [])
                        if isinstance(c, dict) and c.get("id")
                    ]
        except Exception:
            pass

    for c_cfg in custom_models_list:
        cid = str(c_cfg.get("id", "")).strip()
        if not cid or cid in results:
            continue
        c_path_str = c_cfg.get("model_path") or ""
        c_path = Path(c_path_str).expanduser().resolve() if c_path_str else None
        c_driver = str(c_cfg.get("driver") or "funasr").lower()
        c_name = str(c_cfg.get("name") or cid)

        is_ready = bool(c_path and c_path.exists() and verify_model_integrity(c_path, None))
        status = "ready" if is_ready else ("not_found" if not (c_path and c_path.exists()) else "corrupted")

        categories = c_cfg.get("categories") or (["RealtimeASR"] if c_driver == "xasr" else ["FileASR"])
        languages = c_cfg.get("languages") or list(WHISPER_LANGUAGES)
        features = c_cfg.get("features") or ["asrAutoLanguageDetect"]

        results[cid] = ModelScanResult(
            id=cid,
            name=c_name,
            driver=c_driver,
            ms_repo=f"custom/{cid}",
            hf_repo=f"custom/{cid}",
            categories=categories,
            languages=languages,
            status=status,
            model_path=c_path if is_ready else None,
            size_on_disk=_calc_dir_size(c_path) if is_ready and c_path else 0,
            size_expected=0,
            features=features,
            preload=bool(c_cfg.get("preload", False)),
            keep_alive=int(c_cfg.get("keep_alive", 600)),
            is_custom=True,
            extra={"is_custom": True, **c_cfg.get("extra", {})},
        )

    # 3. Include any explicitly configured static models from app_config (if not already present and not custom)
    try:
        from server.core.config import app_config
        for pid, pcfg in app_config.models.items():
            if pid not in results and not getattr(pcfg, "is_custom", False):
                p_path = Path(pcfg.model_path) if pcfg.model_path else None
                is_ready = bool(p_path and p_path.exists())
                results[pid] = ModelScanResult(
                    id=pid,
                    name=pcfg.name or pid,
                    driver=pcfg.driver,
                    ms_repo=f"config/{pid}",
                    hf_repo=f"config/{pid}",
                    categories=["FileASR"] if pcfg.driver != "xasr" else ["RealtimeASR"],
                    languages=pcfg.languages or list(WHISPER_LANGUAGES),
                    status="ready" if is_ready else "not_downloaded",
                    model_path=p_path if is_ready else None,
                    size_on_disk=_calc_dir_size(p_path) if is_ready and p_path else 0,
                    size_expected=0,
                    features=["asrAutoLanguageDetect"],
                    preload=pcfg.preload,
                    keep_alive=pcfg.keep_alive,
                )
    except Exception:
        pass

    return results
