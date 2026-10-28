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

from server.core.manifest import BUILTIN_MODELS, ModelManifest, get_manifest
from server.core.paths import get_models_dir


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

    candidate_names = [
        model_id,
        ms_tail,
        hf_tail,
        f"faster-whisper-{model_id}",
    ]
    if model_id.startswith("whisper-"):
        short = model_id.replace("whisper-", "")
        candidate_names.extend([
            f"faster-whisper-{short}",
            short,
        ])
    elif model_id.startswith("distil-whisper-"):
        short = model_id.replace("distil-whisper-", "")
        candidate_names.extend([
            f"faster-distil-whisper-{short}",
            f"distil-whisper-{short}",
        ])
    if "-en" in model_id:
        dotted = model_id.replace("-en", ".en")
        candidate_names.extend([
            dotted,
            dotted.replace("whisper-", "faster-whisper-"),
            dotted.replace("distil-whisper-", "faster-distil-whisper-"),
        ])
    # Handle X-ASR legacy directory name
    if model_id == "xasr-zh-en":
        candidate_names.append("chunk-160ms-model")

    for base in search_dirs:
        if not base.exists():
            continue
        for name in candidate_names:
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

    # 2. Discover custom models dropped manually into models directory
    search_dirs = _get_search_paths()
    known_paths = {r.model_path.resolve() for r in results.values() if r.model_path}

    for base in search_dirs:
        if not base.exists():
            continue
        try:
            for entry in base.iterdir():
                if not entry.is_dir() or entry.resolve() in known_paths or entry.name in results:
                    continue
                # Determine driver based on contained files
                has_bin = (entry / "model.bin").exists()
                has_onnx = any(entry.glob("*.onnx"))
                has_pt = (entry / "model.pt").exists()

                # Filter out auxiliary non-ASR models (VAD, Punctuation, etc.)
                entry_name_lower = entry.name.lower()
                is_auxiliary = any(
                    kw in entry_name_lower
                    for kw in ("vad", "punc", "punctuation", "fsmn", "voice_activity", "text_postprocess")
                )
                if is_auxiliary:
                    continue

                driver = "whisper" if has_bin else ("funasr" if has_pt else ("xasr" if has_onnx else "unknown"))
                if driver == "unknown":
                    continue

                custom_id = entry.name
                results[custom_id] = ModelScanResult(
                    id=custom_id,
                    name=f"Custom ({custom_id})",
                    driver=driver,
                    repo=f"local/{custom_id}",
                    categories=["FileASR"],
                    languages=["multilingual"],
                    status="ready" if verify_model_integrity(entry, None) else "corrupted",
                    model_path=entry,
                    size_on_disk=_calc_dir_size(entry),
                    size_expected=_calc_dir_size(entry),
                    features=["asrAutoLanguageDetect"],
                    preload=False,
                    keep_alive=600,
                )
        except (PermissionError, FileNotFoundError):
            pass

    # 3. Include any explicitly configured providers from app_config
    try:
        from server.core.config import app_config
        for pid, pcfg in app_config.providers.items():
            if pid not in results:
                p_path = Path(pcfg.model_path) if pcfg.model_path else None
                is_ready = bool(p_path and p_path.exists())
                results[pid] = ModelScanResult(
                    id=pid,
                    name=pcfg.name or pid,
                    driver=pcfg.driver,
                    repo=f"config/{pid}",
                    categories=["FileASR"] if pcfg.driver != "xasr" else ["RealtimeASR"],
                    languages=pcfg.languages or ["multilingual"],
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
