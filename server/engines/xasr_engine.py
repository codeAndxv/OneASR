"""X-ASR 流式语音识别引擎（基于 sherpa-onnx 实现的兼容导出模块）。"""

from server.engines.sherpa_onnx_engine import (
    SherpaOnnxEngine,
    SherpaOnnxEngine as XASREngine,
    SherpaOnnxStreamSession,
    SherpaOnnxStreamSession as XASRStreamingSession,
)

__all__ = [
    "SherpaOnnxEngine",
    "SherpaOnnxStreamSession",
    "XASREngine",
    "XASRStreamingSession",
]
