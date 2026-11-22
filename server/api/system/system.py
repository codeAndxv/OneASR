"""OneASR system diagnostics, hardware detection, and preferences API (/v1/system)."""

import json
import os
from pathlib import Path
import platform
import shutil
import sys
import time
from typing import Any

import psutil
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from server.api.auth import get_api_key
from server.core.config import API_VERSION, app_config, settings
from server.core.paths import get_logs_dir, get_models_dir, get_oneasr_home, get_settings_path

router = APIRouter(prefix="/v1/system", tags=["system"], dependencies=[Depends(get_api_key)])

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
    models_dir: str | None = Field(None, description="Custom models directory path")


def get_local_lan_ip() -> str:
    """获取本机局域网 IPv4 地址（三重保险：国内外公共 DNS 路由探测 + 离线物理网卡遍历）。"""
    import socket

    # 策略 1: 探测常用公共 DNS (国内: 阿里 223.5.5.5, 114; 海外: 谷歌 8.8.8.8, Cloudflare 1.1.1.1)
    # 仅触发 OS 路由表查询默认出口网卡，不实际握手传输网络数据包
    for probe_ip in ["223.5.5.5", "114.114.114.114", "8.8.8.8", "1.1.1.1"]:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect((probe_ip, 80))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
        except Exception:
            pass
        finally:
            s.close()

    # 策略 2: 纯离线/脱网保底（即使电脑完全拔掉外网宽带，直接遍历本地物理网卡）
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127.") and ":" not in ip:
                return ip
    except Exception:
        pass

    return "127.0.0.1"


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

    # Host & Port from settings
    settings_file = get_settings_path()
    host = "127.0.0.1"
    port = 8020
    if settings_file.is_file():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
                if "host" in data:
                    host = str(data["host"])
                if "port" in data:
                    port = int(data["port"])
        except Exception:
            pass

    lan_ip = get_local_lan_ip()

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
        "status": "ok",
        "app_version": settings.app_version,
        "api_version": API_VERSION,
        "uptime_seconds": int(time.time() - START_TIME),
        "host": host,
        "port": port,
        "lan_ip": lan_ip,
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
        "network": {
            "lan_ip": lan_ip,
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
        "lan_ip": get_local_lan_ip(),
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
    if req.models_dir is not None:
        raw_dir = req.models_dir.strip()
        if raw_dir:
            from pathlib import Path
            target_path = Path(raw_dir).expanduser().resolve()
            try:
                target_path.mkdir(parents=True, exist_ok=True)
                updates["models_dir"] = str(target_path)
                app_config.model_dir = target_path
                app_config.refresh_models()
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid or unwritable models directory: {e}")
        else:
            default_dir = (get_oneasr_home() / "models").resolve()
            default_dir.mkdir(parents=True, exist_ok=True)
            updates["models_dir"] = str(default_dir)
            app_config.model_dir = default_dir
            app_config.refresh_models()

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
    raw_path = req.path.strip()
    if raw_path == "models" or raw_path == "~/.oneasr/models":
        target = str(get_models_dir())
    elif raw_path == "logs" or raw_path == "~/.oneasr/logs":
        target = str(get_logs_dir())
    else:
        target = os.path.expanduser(raw_path)

    if os.path.exists(target):
        if platform.system() == "Darwin":
            subprocess.Popen(["open", target])
        elif platform.system() == "Windows":
            os.startfile(target)
        else:
            subprocess.Popen(["xdg-open", target])
        return {"status": "ok", "opened": target}
    return {"status": "not_found", "path": target}


def _parse_version_tuple(v_str: str) -> tuple[int, ...]:
    """Parse version string like '0.1.0' or 'v0.1.0' into tuple of integers."""
    import re
    cleaned = re.sub(r"^[^\d]*", "", (v_str or "").strip())
    parts: list[int] = []
    for part in re.split(r"[-+.]", cleaned):
        if part.isdigit():
            parts.append(int(part))
        else:
            break
    return tuple(parts) if parts else (0, 0, 0)


@router.get("/check-update")
async def check_system_update():
    """Check for latest OneASR release on GitHub."""
    import json
    import urllib.error
    import urllib.request

    current_ver_str = getattr(settings, "app_version", "0.1.0")
    current_tuple = _parse_version_tuple(current_ver_str)

    api_url = "https://api.github.com/repos/codeAndxv/OneASR/releases/latest"
    web_fallback_url = "https://github.com/codeAndxv/OneASR/releases/latest"

    latest_ver_str = current_ver_str
    release_name = f"v{current_ver_str}"
    release_url = f"https://github.com/codeAndxv/OneASR/releases/tag/{current_ver_str}"
    release_notes = ""
    published_at = ""

    # Strategy 1: Call GitHub API
    try:
        req = urllib.request.Request(
            api_url,
            headers={
                "User-Agent": "OneASR-Desktop",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                tag_name = data.get("tag_name", "").strip()
                latest_ver_str = tag_name.lstrip("v")
                release_name = data.get("name") or tag_name
                release_url = data.get("html_url") or release_url
                release_notes = data.get("body") or ""
                published_at = data.get("published_at") or ""
    except Exception:
        # Strategy 2: If rate-limited or API blocked, probe HTTP 302 redirect on releases/latest
        try:
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    return None

            opener = urllib.request.build_opener(NoRedirect)
            req = urllib.request.Request(web_fallback_url, headers={"User-Agent": "OneASR-Desktop"}, method="HEAD")
            try:
                opener.open(req, timeout=5)
            except urllib.error.HTTPError as e:
                if e.code in (301, 302):
                    loc = e.headers.get("Location") or ""
                    if "/releases/tag/" in loc:
                        tag_name = loc.split("/releases/tag/")[-1].strip()
                        latest_ver_str = tag_name.lstrip("v")
                        release_name = f"v{latest_ver_str}"
                        release_url = loc
        except Exception:
            pass

    latest_tuple = _parse_version_tuple(latest_ver_str)
    has_update = latest_tuple > current_tuple

    return {
        "current_version": current_ver_str,
        "latest_version": latest_ver_str,
        "has_update": has_update,
        "release_name": release_name,
        "release_url": release_url,
        "release_notes": release_notes,
        "published_at": published_at,
    }


class RegisterCustomModelRequest(BaseModel):
    """Payload for explicitly registering a local custom model."""

    id: str = Field(..., description="Unique model identifier, e.g. 'my-sherpa'")
    name: str | None = Field(None, description="Display name, defaults to id")
    driver: str = Field(..., description="Inference engine driver ('xasr', 'funasr', 'whisper', 'firered')")
    model_path: str = Field(..., description="Absolute directory path containing model files")
    languages: list[str] = Field(default_factory=lambda: ["zh", "en"])


def _validate_custom_model_dir(driver: str, path: Path) -> tuple[bool, str]:
    """Validate directory existence and critical weights for the given driver."""
    from pathlib import Path

    if not path.exists():
        return False, f"Directory does not exist: {path}"
    if not path.is_dir():
        return False, f"Path is not a directory: {path}"

    driver_lower = driver.lower().strip()
    if driver_lower == "xasr":
        has_tokens = (path / "tokens.txt").exists() or any(path.glob("tokens*.txt"))
        has_encoder = any(path.glob("encoder*.onnx"))
        if not has_tokens or not has_encoder:
            return False, "Sherpa-ONNX model directory must contain 'tokens.txt' and 'encoder*.onnx'."
    elif driver_lower == "funasr":
        has_weights = (
            any((path / fname).exists() for fname in ["model.pt", "model.onnx", "model.pb"])
            or any(path.glob("*.pt"))
            or any(path.glob("*.onnx"))
        )
        if not has_weights:
            return False, "FunASR model directory must contain 'model.pt' or 'model.onnx'."
    elif driver_lower in ("whisper", "faster-whisper"):
        has_weights = (path / "model.bin").exists() or any(path.glob("*.safetensors"))
        if not has_weights:
            return False, "Faster-Whisper model directory must contain 'model.bin' or '*.safetensors'."
    elif driver_lower == "firered":
        has_weights = any(path.glob("*.onnx")) or (path / "tokens.txt").exists()
        if not has_weights:
            return False, "FireRed model directory must contain model files."

    return True, ""


@router.get("/custom-models")
async def list_custom_models():
    """List explicitly registered custom models from settings."""
    settings_file = get_settings_path()
    custom_models = []
    if settings_file.is_file():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                custom_models = data.get("custom_models", [])
        except Exception:
            pass
    return {"custom_models": custom_models}


@router.post("/custom-models")
async def register_custom_model(req: RegisterCustomModelRequest):
    """Register and validate a new custom model."""
    import re
    from pathlib import Path

    clean_id = req.id.strip()
    if not re.match(r"^[a-zA-Z0-9_\-\.]+$", clean_id):
        raise HTTPException(
            status_code=400,
            detail="Model ID must only contain alphanumeric characters, hyphens, underscores, or dots.",
        )

    from server.core.manifest import BUILTIN_MODELS
    if clean_id in BUILTIN_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Model ID '{clean_id}' conflicts with a built-in model.",
        )

    clean_driver = req.driver.strip().lower()
    valid_drivers = {"xasr", "funasr", "whisper", "faster-whisper", "firered"}
    if clean_driver not in valid_drivers:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported driver: '{clean_driver}'. Supported: {sorted(list(valid_drivers))}",
        )
    if clean_driver == "faster-whisper":
        clean_driver = "whisper"

    target_path = Path(os.path.expanduser(req.model_path.strip())).resolve()
    valid, err_msg = _validate_custom_model_dir(clean_driver, target_path)
    if not valid:
        raise HTTPException(status_code=400, detail=err_msg)

    settings_file = get_settings_path()
    current_settings: dict[str, Any] = {}
    if settings_file.is_file():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                current_settings = json.load(f) or {}
        except Exception:
            pass

    custom_list: list[dict[str, Any]] = current_settings.get("custom_models", [])
    new_entry = {
        "id": clean_id,
        "name": (req.name or clean_id).strip(),
        "driver": clean_driver,
        "model_path": str(target_path),
        "languages": req.languages or ["zh", "en"],
    }
    custom_list = [c for c in custom_list if c.get("id") != clean_id]
    custom_list.append(new_entry)

    app_config.save_settings({"custom_models": custom_list})
    app_config.refresh_models()

    return {
        "status": "registered",
        "model": new_entry,
    }


@router.delete("/custom-models/{model_id}")
async def unregister_custom_model(model_id: str):
    """Unregister a custom model (removes from settings, does NOT delete disk files)."""
    import asyncio
    from server.engines.registry import unload_engine

    try:
        await asyncio.to_thread(unload_engine, model_id, force=True)
    except Exception:
        pass

    settings_file = get_settings_path()
    current_settings: dict[str, Any] = {}
    if settings_file.is_file():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                current_settings = json.load(f) or {}
        except Exception:
            pass

    custom_list: list[dict[str, Any]] = current_settings.get("custom_models", [])
    filtered_list = [c for c in custom_list if c.get("id") != model_id]

    if len(filtered_list) == len(custom_list):
        raise HTTPException(status_code=404, detail=f"Custom model '{model_id}' not found.")

    app_config.save_settings({"custom_models": filtered_list})
    app_config.refresh_models()

    return {
        "status": "unregistered",
        "id": model_id,
    }
