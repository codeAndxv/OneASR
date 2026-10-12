from unittest.mock import MagicMock, patch
import pytest

from server.core.config import EngineConfig
from server.engines.funasr_engine import FunASREngine


@pytest.mark.asyncio
async def test_funasr_engine_mocked_transcribe():
    cfg = EngineConfig("funasr", {"model_name": "paraformer-zh", "device": "cpu"})
    engine = FunASREngine(cfg)

    # 模拟 AutoModel
    mock_model = MagicMock()
    mock_model.generate.return_value = [
        {
            "text": "你好世界欢迎使用语音识别",
            "sentence_info": [
                {
                    "text": "你好世界",
                    "start": 0,
                    "end": 1200,
                    "timestamp": [[0, 300], [300, 600], [600, 900], [900, 1200]],
                },
                {
                    "text": "欢迎使用语音识别",
                    "start": 1300,
                    "end": 3500,
                    "timestamp": [[1300, 2000], [2000, 3500]],
                },
            ],
        }
    ]

    with patch.object(engine, "_get_model", return_value=mock_model):
        text, segments = await engine.transcribe_file(b"fake-pcm-data")
        assert text == "你好世界欢迎使用语音识别"
        assert len(segments) == 2
        assert segments[0].text == "你好世界"
        assert segments[0].start == 0.0
        assert segments[0].end == 1.2
        assert segments[1].text == "欢迎使用语音识别"
        assert segments[1].start == 1.3
        assert segments[1].end == 3.5


@pytest.mark.asyncio
async def test_funasr_engine_missing_dependency():
    cfg = EngineConfig("funasr", {"model_name": "paraformer-zh", "device": "cpu"})
    engine = FunASREngine(cfg)

    # 当 funasr 库不存在时应优雅报错并给出安装指引
    with patch.dict("sys.modules", {"funasr": None}):
        with pytest.raises(RuntimeError) as exc_info:
            engine._get_model()
        assert "未安装 funasr" in str(exc_info.value)
