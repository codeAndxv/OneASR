"""OneASR Extended models capability matrix, lifecycle, and dynamic pull/delete API (/v1/x/models)."""

import asyncio
import json
import logging
import shutil
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from server.api.auth import get_api_key
from server.core.config import API_VERSION, app_config
from server.core.errors import OpenAIAPIException
from server.core.manifest import BUILTIN_MODELS, get_manifest
from server.core.paths import get_models_dir
from server.core.scanner import scan_all_models
from server.engines.registry import (
    get_engine,
    get_model_runtime_status,
    unload_engine,
)
from server.utils.downloader import model_downloader

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/x/models", tags=["x-models"], dependencies=[Depends(get_api_key)])


class PullModelRequest(BaseModel):
    """Payload for downloading a model via SSE."""

    model_id: str = Field(..., description="ID or alias of the model to download")
    source: str = Field("auto", description="Download source ('auto', 'modelscope', 'hf-mirror', 'huggingface')")


class CancelPullRequest(BaseModel):
    """Payload for cancelling an active model download."""

    model_id: str = Field(..., description="ID or alias of the model download to cancel")


@router.get("")
async def list_extended_models():
    """Return all models in catalog (ready, not downloaded, and downloading) with full capability matrix."""
    scanned = scan_all_models()
    models: list[dict[str, Any]] = []

    for model_id, scan_res in scanned.items():
        base_config = app_config.models.get(model_id)
        rt_status = get_model_runtime_status(model_id) if base_config else {
            "loaded": False,
            "active_tasks": 0,
            "keep_alive": scan_res.keep_alive,
            "preload": scan_res.preload,
            "last_used_at": None,
        }

        # Check if an active download task is in progress
        active_task = model_downloader.get_task(model_id)
        current_status = scan_res.status
        download_progress = None

        if active_task and active_task.status in ("pending", "downloading", "verifying"):
            current_status = active_task.status
            download_progress = {
                "percent": active_task.percent,
                "downloaded_bytes": active_task.downloaded_bytes,
                "total_bytes": active_task.total_bytes,
                "speed": active_task.speed_str,
                "eta_seconds": active_task.eta_seconds,
            }

        models.append({
            "id": model_id,
            "name": scan_res.name,
            "object": "model",
            "created": int(time.time()),
            "owned_by": scan_res.driver,
            "status": current_status,  # "ready", "not_downloaded", "downloading", "corrupted"
            "download_progress": download_progress,
            "categories": scan_res.categories,
            "functions": scan_res.categories,
            "languages": scan_res.languages,
            "features": scan_res.features,
            "size_on_disk": scan_res.size_on_disk,
            "size_expected": scan_res.size_expected,
            "model_path": str(scan_res.model_path) if scan_res.model_path else None,
            "loaded": rt_status["loaded"],
            "active_tasks": rt_status["active_tasks"],
            "keep_alive": rt_status["keep_alive"],
            "preload": rt_status["preload"],
            "last_used_at": rt_status["last_used_at"],
        })

    logger.info("[x-models] Catalog listing: total %d models", len(models))
    return {
        "object": "list",
        "api_version": API_VERSION,
        "data": models,
    }


@router.get("/{model_id}")
async def retrieve_extended_model(model_id: str):
    """Return capability matrix and runtime details for a single model."""
    manifest = get_manifest(model_id)
    canonical_id = manifest.id if manifest else model_id

    scanned = scan_all_models()
    scan_res = scanned.get(canonical_id)

    if not scan_res:
        raise OpenAIAPIException(
            status_code=404,
            message=f"The model '{model_id}' does not exist in catalog.",
            error_type="invalid_request_error",
            param="model",
            code="model_not_found",
        )

    base_config = app_config.models.get(canonical_id)
    rt_status = get_model_runtime_status(canonical_id) if base_config else {
        "loaded": False,
        "active_tasks": 0,
        "keep_alive": scan_res.keep_alive,
        "preload": scan_res.preload,
        "last_used_at": None,
    }

    active_task = model_downloader.get_task(canonical_id)
    current_status = scan_res.status
    download_progress = None
    if active_task and active_task.status in ("pending", "downloading", "verifying"):
        current_status = active_task.status
        download_progress = {
            "percent": active_task.percent,
            "downloaded_bytes": active_task.downloaded_bytes,
            "total_bytes": active_task.total_bytes,
            "speed": active_task.speed_str,
            "eta_seconds": active_task.eta_seconds,
        }

    return {
        "id": canonical_id,
        "name": scan_res.name,
        "object": "model",
        "created": int(time.time()),
        "owned_by": scan_res.driver,
        "status": current_status,
        "download_progress": download_progress,
        "categories": scan_res.categories,
        "functions": scan_res.categories,
        "languages": scan_res.languages,
        "features": scan_res.features,
        "size_on_disk": scan_res.size_on_disk,
        "size_expected": scan_res.size_expected,
        "model_path": str(scan_res.model_path) if scan_res.model_path else None,
        "loaded": rt_status["loaded"],
        "active_tasks": rt_status["active_tasks"],
        "keep_alive": rt_status["keep_alive"],
        "preload": rt_status["preload"],
        "last_used_at": rt_status["last_used_at"],
    }


@router.post("/pull")
async def pull_model_endpoint(req: PullModelRequest):
    """Trigger an asynchronous model download with real-time SSE progress streaming."""
    manifest = get_manifest(req.model_id)
    if not manifest:
        raise OpenAIAPIException(
            status_code=404,
            message=f"Model '{req.model_id}' is not in the official catalog.",
            error_type="invalid_request_error",
            param="model",
            code="model_not_found",
        )

    async def sse_event_stream():
        async for event in model_downloader.stream_download(manifest.id, req.source):
            yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"

    return StreamingResponse(
        sse_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/cancel")
async def cancel_pull_endpoint(req: CancelPullRequest):
    """Cancel an active background model download."""
    manifest = get_manifest(req.model_id)
    target_id = manifest.id if manifest else req.model_id

    cancelled = model_downloader.cancel_download(target_id)
    return {
        "id": target_id,
        "cancelled": cancelled,
        "status": "cancelled" if cancelled else "not_active",
    }


@router.delete("/{model_id}")
async def delete_model_endpoint(model_id: str):
    """Unload model from memory if resident and delete its weights directory from disk."""
    manifest = get_manifest(model_id)
    target_id = manifest.id if manifest else model_id

    # 1. Unload from memory if currently resident
    rt = get_model_runtime_status(target_id)
    if rt and rt["loaded"]:
        try:
            await asyncio.to_thread(unload_engine, target_id, force=True)
            logger.info("Unloaded model %s before deletion", target_id)
        except Exception as e:
            logger.warning("Error unloading model %s: %s", target_id, e)

    # 2. Locate directory on disk
    scanned = scan_all_models()
    scan_res = scanned.get(target_id)
    if not scan_res or not scan_res.model_path or not scan_res.model_path.exists():
        raise OpenAIAPIException(
            status_code=404,
            message=f"Model '{model_id}' is not downloaded locally.",
            error_type="invalid_request_error",
            param="model",
            code="model_not_found",
        )

    model_path = scan_res.model_path
    try:
        if model_path.is_dir():
            shutil.rmtree(model_path)
            logger.info("Deleted model directory: %s", model_path)
        elif model_path.is_file():
            model_path.unlink()

        # 3. Refresh app config
        app_config.refresh_models()
        return {
            "id": target_id,
            "status": "deleted",
            "deleted_path": str(model_path),
        }
    except Exception as e:
        logger.error("Failed to delete model directory %s: %s", model_path, e)
        raise OpenAIAPIException(
            status_code=500,
            message=f"Failed to delete model directory: {e}",
            error_type="server_error",
            code="delete_failed",
        )


@router.post("/{model_id}/load")
async def load_model_endpoint(model_id: str):
    """Manually preheat and load model weights into RAM/VRAM."""
    manifest = get_manifest(model_id)
    target_id = manifest.id if manifest else model_id

    if target_id not in app_config.models:
        raise OpenAIAPIException(
            status_code=404,
            message=f"The model '{model_id}' does not exist.",
            error_type="invalid_request_error",
            param="model",
            code="model_not_found",
        )
    t0 = time.time()
    await asyncio.to_thread(get_engine, target_id)
    elapsed = round(time.time() - t0, 3)
    rt = get_model_runtime_status(target_id)
    logger.info("[x-models] Manually loaded model: %s, time=%.3fs", target_id, elapsed)
    return {
        "id": target_id,
        "status": "loaded",
        "loaded": rt["loaded"],
        "load_time_seconds": elapsed,
        "keep_alive": rt["keep_alive"],
    }


@router.post("/{model_id}/unload")
async def unload_model_endpoint(
    model_id: str,
    force: bool = Query(False, description="Force unload even if active_tasks > 0"),
):
    """Manually evict model weights from RAM/VRAM."""
    manifest = get_manifest(model_id)
    target_id = manifest.id if manifest else model_id

    if target_id not in app_config.models:
        raise OpenAIAPIException(
            status_code=404,
            message=f"The model '{model_id}' does not exist.",
            error_type="invalid_request_error",
            param="model",
            code="model_not_found",
        )
    try:
        was_loaded = await asyncio.to_thread(unload_engine, target_id, force)
    except RuntimeError as e:
        raise OpenAIAPIException(
            status_code=409,
            message=str(e),
            error_type="invalid_request_error",
            param="model",
            code="model_in_use",
        )

    rt = get_model_runtime_status(target_id)
    logger.info("[x-models] Unloaded model: %s, was_loaded=%s", target_id, was_loaded)
    return {
        "id": target_id,
        "status": "unloaded",
        "was_loaded": was_loaded,
        "loaded": rt["loaded"],
    }
