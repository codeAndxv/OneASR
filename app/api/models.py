"""引擎和模型信息 API。"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.auth import get_api_key
from app.core.config import app_config
from app.engines.registry import get_loaded_engines, load_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["models"], dependencies=[Depends(get_api_key)])


class LoadEngineRequest(BaseModel):
    """加载引擎请求。"""
    engine: str = Field(..., description="引擎名称，如 faster-whisper")
    model: str = Field(..., description="模型名称，如 medium, large-v3")
    device: str = Field("cpu", description="设备：cpu 或 cuda")
    compute_type: str = Field("int8", description="计算精度：int8, float16, int8_float16 等")


@router.get("/engines")
async def list_engines():
    """返回已加载的引擎及其模型信息。"""
    loaded = get_loaded_engines()
    engines = []

    for key, info in loaded.items():
        base_config = app_config.engines.get(info.engine_name)
        engines.append({
            "id": info.engine_name,
            "model": info.model_name,
            "device": info.device,
            "compute_type": info.compute_type,
            "type": base_config.type if base_config else "unknown",
            "streaming": info.streaming,
            "loaded": True,
        })

    return {
        "object": "list",
        "data": engines,
        "default": app_config.default_engine,
    }


@router.post("/engines/load")
async def api_load_engine(req: LoadEngineRequest):
    """加载指定引擎和模型。

    传入引擎名、模型名及设备参数，服务端创建并缓存模型实例。
    已加载的实例会直接返回，不会重复加载。

    示例请求：
    ```json
    {
        "engine": "faster-whisper",
        "model": "medium",
        "device": "cpu",
        "compute_type": "int8"
    }
    ```
    """
    try:
        loaded = load_engine(
            engine_name=req.engine,
            model_name=req.model,
            device=req.device,
            compute_type=req.compute_type,
        )
        return {
            "status": "ok",
            "engine": loaded.engine_name,
            "model": loaded.model_name,
            "device": loaded.device,
            "compute_type": loaded.compute_type,
            "streaming": loaded.streaming,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("引擎加载失败: %s", e)
        raise HTTPException(status_code=500, detail=f"引擎加载失败: {e}")
