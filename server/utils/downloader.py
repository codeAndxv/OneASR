"""Asynchronous model download manager and progress streaming engine.

Coordinates downloads using official ModelScope and HuggingFace SDKs,
providing auto-fallback, progress tracking, cancellation, and Server-Sent Events (SSE)
integration without requiring external CLI dependencies.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncGenerator

from server.core.config import app_config
from server.core.manifest import ModelManifest, get_manifest
from server.core.paths import get_models_dir, get_settings_path
from server.core.scanner import verify_model_integrity

logger = logging.getLogger(__name__)


@dataclass
class DownloadTask:
    """Represents a model download operation and its real-time progress state."""

    model_id: str
    target_dir: Path
    status: str = "pending"  # "pending", "downloading", "verifying", "completed", "failed", "cancelled"
    source: str = "auto"
    percent: float = 0.0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed_bytes_sec: float = 0.0
    speed_str: str = "0 B/s"
    eta_seconds: int = 0
    error_message: str = ""
    cancel_event: threading.Event = field(default_factory=threading.Event)
    listeners: list[asyncio.Queue] = field(default_factory=list)


def _format_size(size_bytes: int | float) -> str:
    """Format bytes into human-readable string (KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes:.0f} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


class ModelDownloader:
    """Central singleton service for asynchronous model downloads."""

    def __init__(self):
        self._tasks: dict[str, DownloadTask] = {}
        self._lock = threading.Lock()

    def get_task(self, model_id: str) -> DownloadTask | None:
        """Retrieve an ongoing or recently finished task."""
        with self._lock:
            return self._tasks.get(model_id)

    def cancel_download(self, model_id: str) -> bool:
        """Signal cancellation for an active download task and clean up temporary files."""
        with self._lock:
            task = self._tasks.get(model_id)
            if not task or task.status in ("completed", "failed", "cancelled"):
                return False
            task.cancel_event.set()
            task.status = "cancelled"
            logger.info("Download task for %s cancelled by user request", model_id)

        # Remove lock marker and temporary files
        lock_file = task.target_dir / ".downloading"
        if lock_file.exists():
            try:
                lock_file.unlink()
            except OSError:
                pass
        return True

    def _measure_dir_size(self, path: Path) -> int:
        """Calculate bytes written to the directory so far."""
        if not path.exists():
            return 0
        total = 0
        try:
            for entry in os.scandir(path):
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat().st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += self._measure_dir_size(Path(entry.path))
        except (PermissionError, FileNotFoundError):
            pass
        return total

    def _execute_download_sync(self, task: DownloadTask, manifest: ModelManifest, source: str) -> None:
        """Run the actual SDK download in a dedicated background worker thread."""
        target_dir = task.target_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        lock_file = target_dir / ".downloading"
        lock_file.touch(exist_ok=True)

        task.status = "downloading"
        task.total_bytes = manifest.size_bytes or (500 * 1024 * 1024)

        # Handle sub-directory extraction if required (e.g. X-ASR subfolder in repo)
        subdir = manifest.extra.get("subdir_in_repo")
        if subdir:
            staging_dir = target_dir.parent / f".staging_{target_dir.name}"
            staging_dir.mkdir(parents=True, exist_ok=True)
            download_dest = staging_dir
            allow_patterns = [f"{subdir.strip('/')}/*"]
        else:
            staging_dir = None
            download_dest = target_dir
            allow_patterns = None

        # Resolve preferred source from settings.json if source is auto
        preferred_source = "auto"
        settings_file = get_settings_path()
        if settings_file.is_file():
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    preferred_source = (json.load(f) or {}).get("download_source", "auto")
            except Exception:
                pass

        active_source = source if source != "auto" else preferred_source

        if active_source == "huggingface":
            candidate_sources = ["huggingface", "hf-mirror", "modelscope"]
        elif active_source == "hf-mirror":
            candidate_sources = ["hf-mirror", "huggingface", "modelscope"]
        elif active_source == "modelscope":
            candidate_sources = ["modelscope", "hf-mirror", "huggingface"]
        else:
            candidate_sources = ["modelscope", "hf-mirror", "huggingface"]

        last_error = None
        success = False

        # Progress monitor loop in a background daemon thread
        stop_monitor = threading.Event()

        def _monitor_progress():
            t_last = time.time()
            bytes_last = 0
            while not stop_monitor.is_set() and not task.cancel_event.is_set():
                time.sleep(0.5)
                current_bytes = self._measure_dir_size(download_dest)
                now = time.time()
                dt = max(0.001, now - t_last)
                delta_bytes = max(0, current_bytes - bytes_last)
                speed = delta_bytes / dt

                task.downloaded_bytes = current_bytes
                task.speed_bytes_sec = speed
                task.speed_str = f"{_format_size(speed)}/s"

                if task.total_bytes > 0:
                    task.percent = min(99.0, round((current_bytes / task.total_bytes) * 100, 1))
                    remaining = max(0, task.total_bytes - current_bytes)
                    task.eta_seconds = int(remaining / speed) if speed > 1024 else 0

                t_last = now
                bytes_last = current_bytes

        monitor_thread = threading.Thread(target=_monitor_progress, daemon=True)
        monitor_thread.start()

        try:
            for src in candidate_sources:
                if task.cancel_event.is_set():
                    task.status = "cancelled"
                    return

                try:
                    task.source = src
                    logger.info("Starting download for %s using source: %s", manifest.id, src)

                    if src == "modelscope":
                        from modelscope import snapshot_download as ms_download

                        ms_download(
                            model_id=manifest.ms_repo,
                            local_dir=str(download_dest),
                            allow_patterns=allow_patterns,
                        )
                    elif src in ("hf-mirror", "huggingface"):
                        from huggingface_hub import snapshot_download as hf_download

                        endpoint = "https://hf-mirror.com" if src == "hf-mirror" else os.getenv("HF_ENDPOINT")
                        hf_download(
                            repo_id=manifest.hf_repo,
                            local_dir=str(download_dest),
                            allow_patterns=allow_patterns,
                            endpoint=endpoint,
                        )
                    success = True
                    break
                except Exception as e:
                    last_error = e
                    logger.warning("Download failed for %s from %s: %s", manifest.id, src, e)

            # Extract subfolder if required
            if success and staging_dir and subdir:
                extracted = staging_dir / subdir.strip("/")
                if extracted.exists():
                    for item in extracted.iterdir():
                        dest_item = target_dir / item.name
                        if dest_item.exists():
                            if dest_item.is_dir():
                                shutil.rmtree(dest_item)
                            else:
                                dest_item.unlink()
                        shutil.move(str(item), str(dest_item))

        finally:
            stop_monitor.set()
            if staging_dir and staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)

        if task.cancel_event.is_set():
            task.status = "cancelled"
            if lock_file.exists():
                lock_file.unlink()
            return

        if not success:
            task.status = "failed"
            task.error_message = str(last_error or "All candidate download sources failed")
            if lock_file.exists():
                lock_file.unlink()
            return

        # Verification step
        task.status = "verifying"
        task.percent = 99.9
        if verify_model_integrity(target_dir, manifest):
            task.status = "completed"
            task.percent = 100.0
            if lock_file.exists():
                lock_file.unlink()
            # Dynamically update the app config without restarting server
            app_config.refresh_models()
            logger.info("Model %s downloaded and verified successfully at %s", manifest.id, target_dir)
        else:
            task.status = "failed"
            task.error_message = "File integrity check failed after download"
            if lock_file.exists():
                lock_file.unlink()

    async def stream_download(
        self, model_id: str, source: str = "auto"
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Initiate or attach to a download task, yielding real-time SSE progress events."""
        manifest = get_manifest(model_id)
        if not manifest:
            yield {
                "event": "error",
                "data": {"model_id": model_id, "error": f"Unknown model id: {model_id}"},
            }
            return

        dest_dir = get_models_dir() / manifest.id

        with self._lock:
            existing = self._tasks.get(manifest.id)
            if existing and existing.status in ("pending", "downloading", "verifying"):
                task = existing
            else:
                task = DownloadTask(model_id=manifest.id, target_dir=dest_dir, source=source)
                self._tasks[manifest.id] = task
                worker = threading.Thread(
                    target=self._execute_download_sync,
                    args=(task, manifest, source),
                    daemon=True,
                )
                worker.start()

        # Stream status updates until terminal state
        while True:
            payload = {
                "model_id": task.model_id,
                "status": task.status,
                "source": task.source,
                "percent": task.percent,
                "downloaded_bytes": task.downloaded_bytes,
                "downloaded_str": _format_size(task.downloaded_bytes),
                "total_bytes": task.total_bytes,
                "total_str": _format_size(task.total_bytes),
                "speed": task.speed_str,
                "eta_seconds": task.eta_seconds,
            }

            if task.status == "completed":
                yield {"event": "done", "data": payload}
                break
            elif task.status == "failed":
                payload["error"] = task.error_message
                yield {"event": "error", "data": payload}
                break
            elif task.status == "cancelled":
                payload["error"] = "Download cancelled by user"
                yield {"event": "cancelled", "data": payload}
                break
            else:
                yield {"event": "progress", "data": payload}

            await asyncio.sleep(0.5)


# Global downloader singleton
model_downloader = ModelDownloader()
