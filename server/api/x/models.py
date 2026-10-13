"""OneASR Extended models capability matrix & lifecycle API (/v1/x/models)."""

import asyncio
import logging
import time

from fastapi import APIRouter, Depends, Query

from server.api.auth import get_api_key
from server.core.config import API_VERSION, app_config
from server.core.errors import OpenAIAPIException
from server.engines.registry import (
    get_engine,
    get_provider_runtime_status,
    unload_engine,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/x/models", tags=["x-models"], dependencies=[Depends(get_api_key)])


@router.get("")
async def list_extended_models():
    """返回所有已启用的模型完整能力矩阵（支持语种、特性分类）与实时显存/内存驻留状态。"""
    models = []
    for name, base_config in app_config.providers.items():
        if not getattr(base_config, "enable", True):
            continue
        rt_status = get_provider_runtime_status(name)
        models.append({
            "id": name,
            "object": "model",
            "created": int(time.time()),
            "owned_by": base_config.type if base_config else "unknown",
            "shutdown_date": "9999-12-31T23:59:59Z",
            "categories": base_config.categories if base_config else [],
            "functions": base_config.categories if base_config else [],
            "languages": base_config.languages if base_config else [],
            "features": base_config.features if base_config else ["asrAutoLanguageDetect"],
            "loaded": rt_status["loaded"],
            "active_tasks": rt_status["active_tasks"],
            "keep_alive": rt_status["keep_alive"],
            "preload": rt_status["preload"],
            "last_used_at": rt_status["last_used_at"],
        })

    model_names = [f"{m['id']}({'loaded' if m['loaded'] else 'standby'})" for m in models]
    logger.info("[x-models] 查询扩展模型列表: 共 %d 个 (%s)", len(models), ", ".join(model_names) if model_names else "无")

    return {
        "object": "list",
        "api_version": API_VERSION,
        "data": models,
    }


@router.get("/{model_id}")
async def retrieve_extended_model(model_id: str):
    """返回单个模型的完整能力矩阵与运行态详情。"""
    if model_id not in app_config.providers or not getattr(app_config.providers[model_id], "enable", True):
        raise OpenAIAPIException(
            status_code=404,
            message=f"The model '{model_id}' does not exist.",
            error_type="invalid_request_error",
            param="model",
            code="model_not_found",
        )
    base_config = app_config.providers[model_id]
    rt_status = get_provider_runtime_status(model_id)
    return {
        "id": model_id,
        "object": "model",
        "created": int(time.time()),
        "owned_by": base_config.type if base_config else "unknown",
        "shutdown_date": "9999-12-31T23:59:59Z",
        "categories": base_config.categories if base_config else [],
        "functions": base_config.categories if base_config else [],
        "languages": base_config.languages if base_config else [],
        "features": base_config.features if base_config else ["asrAutoLanguageDetect"],
        "loaded": rt_status["loaded"],
        "active_tasks": rt_status["active_tasks"],
        "keep_alive": rt_status["keep_alive"],
        "preload": rt_status["preload"],
        "last_used_at": rt_status["last_used_at"],
    }


@router.post("/{model_id}/load")
async def load_model_endpoint(model_id: str):
    """手动将指定模型预热加载到内存/显存中。"""
    if model_id not in app_config.providers:
        raise OpenAIAPIException(
            status_code=404,
            message=f"The model '{model_id}' does not exist.",
            error_type="invalid_request_error",
            param="model",
            code="model_not_found",
        )
    t0 = time.time()
    await asyncio.to_thread(get_engine, model_id)
    elapsed = round(time.time() - t0, 3)
    rt = get_provider_runtime_status(model_id)
    logger.info("[x-models] 手动加载模型成功: model_id=%s, 耗时=%.3fs", model_id, elapsed)
    return {
        "id": model_id,
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
    """手动卸载指定模型并释放内存/显存。"""
    if model_id not in app_config.providers:
        raise OpenAIAPIException(
            status_code=404,
            message=f"The model '{model_id}' does not exist.",
            error_type="invalid_request_error",
            param="model",
            code="model_not_found",
        )
    try:
        was_loaded = await asyncio.to_thread(unload_engine, model_id, force)
    except RuntimeError as e:
        raise OpenAIAPIException(
            status_code=409,
            message=str(e),
            error_type="invalid_request_error",
            param="model",
            code="model_in_use",
        )

    rt = get_provider_runtime_status(model_id)
    logger.info("[x-models] 手动卸载模型完成: model_id=%s, was_loaded=%s", model_id, was_loaded)
    return {
        "id": model_id,
        "status": "unloaded",
        "was_loaded": was_loaded,
        "loaded": rt["loaded"],
    }
