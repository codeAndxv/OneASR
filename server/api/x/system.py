"""OneASR system diagnostics, hardware detection, and preferences API (/v1/x/system)."""

import os
import platform
import shutil
import sys
import time
from typing import Any

import psutil
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from server.api.auth import get_api_key
from server.core.config import API_VERSION, app_config, settings
from server.core.paths import get_models_dir, get_oneasr_home, get_settings_path

router = APIRouter(prefix="/v1/x/system", tags=["x-system"], dependencies=[Depends(get_api_key)])

START_TIME = time.time()


class UpdateSettingsRequest(BaseModel):
    """Payload for updating user preferences."""

    host: str | None = Field(None, description="Host address binding (e.g. '127.0.0.1')")
    port: int | None = Field(None, description="Port number (e.g. 8020)")
    default_model: str | None = Field(None, description="Default ASR model identifier")
    keep_alive: int | None = Field(None, description="Model residency timeout in seconds (-1 for permanent)")
    keep_alive_timeout: int | None = Field(None, description="Alias for keep_alive")
    max_loaded_models: int | None = Field(None, description="Maximum concurrent loaded models in memory (LRU)")
    api_key: str | None = Field(None, description="Optional API key for client authentication")
    download_source: str | None = Field(None, description="Preferred model download source ('modelscope', 'huggingface', 'hf-mirror', 'auto')")
    vad_threshold: float | None = Field(None, description="VAD speech detection sensitivity threshold (0.1 - 0.9)")
    target_chunk_duration: float | None = Field(None, description="Long audio target chunk duration in seconds (3.0 - 15.0)")


def _detect_accelerator() -> dict[str, Any]:
    """Detect available hardware inference accelerators (MPS, CUDA, CPU)."""
    device_type = "cpu"
    device_name = platform.processor() or "CPU"
    total_vram_mb = 0

    try:
        import torch

        if torch.cuda.is_available():
            device_type = "cuda"
            device_name = torch.cuda.get_device_name(0)
            total_vram_mb = int(torch.cuda.get_device_properties(0).total_memory / (1024 * 1024))
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device_type = "mps"
            device_name = f"Apple Silicon ({platform.machine()})"
    except Exception:
        pass

    return {
        "accelerator": device_type,  # "cuda", "mps", "cpu"
        "device_name": device_name,
        "vram_total_mb": total_vram_mb,
    }


@router.get("/info")
async def get_system_info():
    """Return hardware specs, accelerator status, storage utilization, and server uptime."""
    accel = _detect_accelerator()
    home_dir = get_oneasr_home()
    models_dir = get_models_dir()

    # Disk usage for the drive holding ~/.oneasr
    disk_total_gb = 0.0
    disk_free_gb = 0.0
    try:
        disk_usage = shutil.disk_usage(home_dir)
        disk_total_gb = round(disk_usage.total / (1024**3), 1)
        disk_free_gb = round(disk_usage.free / (1024**3), 1)
    except Exception:
        pass

    # RAM usage
    mem = psutil.virtual_memory()

    return {
        "service": "OneASR",
        "app_version": settings.app_version,
        "api_version": API_VERSION,
        "uptime_seconds": int(time.time() - START_TIME),
        "platform": {
            "os": platform.system(),
            "os_release": platform.release(),
            "arch": platform.machine(),
            "python": platform.python_version(),
        },
        "hardware": {
            "cpu_cores": psutil.cpu_count(logical=True),
            "ram_total_mb": int(mem.total / (1024 * 1024)),
            "ram_available_mb": int(mem.available / (1024 * 1024)),
            "ram_percent": mem.percent,
            **accel,
        },
        "storage": {
            "oneasr_home": str(home_dir),
            "models_dir": str(models_dir),
            "disk_total_gb": disk_total_gb,
            "disk_free_gb": disk_free_gb,
        },
    }


@router.get("/settings")
async def get_system_settings():
    """Return active server settings and current preferences."""
    settings_file = get_settings_path()
    file_settings: dict[str, Any] = {}
    if settings_file.is_file():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                file_settings = json.load(f) or {}
        except Exception:
            pass

    return {
        "host": file_settings.get("host", "127.0.0.1"),
        "port": file_settings.get("port", 8020),
        "api_key": app_config.api_key,
        "keep_alive": app_config.model_manager.default_keep_alive,
        "keep_alive_timeout": app_config.model_manager.default_keep_alive,
        "default_keep_alive": app_config.model_manager.default_keep_alive,
        "max_loaded_models": app_config.model_manager.max_loaded_models,
        "download_source": file_settings.get("download_source"),
        "vad_threshold": getattr(app_config.asr_toolkit.vad, "threshold", 0.5),
        "target_chunk_duration": getattr(app_config.asr_toolkit.chunking, "target_chunk_duration", 6.0),
        "models_dir": str(get_models_dir()),
        "settings_file": str(get_settings_path()),
    }


@router.post("/settings")
async def update_system_settings(req: UpdateSettingsRequest):
    """Update settings and atomically write them into ~/.oneasr/settings.json."""
    updates: dict[str, Any] = {}
    if req.host is not None:
        updates["host"] = req.host
    if req.port is not None:
        updates["port"] = req.port
    if req.default_model is not None:
        updates["default_model"] = req.default_model
    if req.download_source is not None:
        updates["download_source"] = req.download_source
    ka = req.keep_alive if req.keep_alive is not None else req.keep_alive_timeout
    if ka is not None:
        updates["keep_alive"] = ka
        app_config.model_manager.default_keep_alive = ka
    if req.max_loaded_models is not None:
        updates["max_loaded_models"] = req.max_loaded_models
        app_config.model_manager.max_loaded_models = req.max_loaded_models
    if req.api_key is not None:
        updates["api_key"] = req.api_key
        app_config.api_key = req.api_key
    if req.vad_threshold is not None:
        updates["vad_threshold"] = req.vad_threshold
        if hasattr(app_config.asr_toolkit, "vad"):
            app_config.asr_toolkit.vad.threshold = req.vad_threshold
    if req.target_chunk_duration is not None:
        updates["target_chunk_duration"] = req.target_chunk_duration
        if hasattr(app_config.asr_toolkit, "chunking"):
            app_config.asr_toolkit.chunking.target_chunk_duration = req.target_chunk_duration

    app_config.save_settings(updates)
    return {
        "status": "updated",
        "saved_settings": updates,
    }


class OpenPathRequest(BaseModel):
    path: str = Field(..., description="Target directory path to open in system file manager")


@router.post("/open-path")
async def open_system_path(req: OpenPathRequest):
    """Open specified directory or file in host OS file explorer (Finder, Windows Explorer, XDG)."""
    import subprocess
    target = os.path.expanduser(req.path)
    if os.path.exists(target):
        if platform.system() == "Darwin":
            subprocess.Popen(["open", target])
        elif platform.system() == "Windows":
            os.startfile(target)
        else:
            subprocess.Popen(["xdg-open", target])
        return {"status": "ok", "opened": target}
    return {"status": "not_found", "path": target}

