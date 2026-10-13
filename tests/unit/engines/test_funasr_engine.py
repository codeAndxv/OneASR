"""FunASREngine 单元测试（Mock 底层 AutoModel）。"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from server.core.config import EngineConfig
from server.engines.funasr_engine import FunASREngine

pytestmark = pytest.mark.unit


async def test_funasr_engine_mocked_transcribe(tmp_path: Path):
    cfg = EngineConfig(
        "funasr",
        {
            "model_name": "iic/SenseVoiceSmall",
            "model_path": str(tmp_path),
            "device": "cpu",
        },
    )
    engine = FunASREngine(cfg)

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


async def test_funasr_engine_missing_dependency(tmp_path: Path):
    cfg = EngineConfig(
        "funasr",
        {
            "model_name": "iic/SenseVoiceSmall",
            "model_path": str(tmp_path),
            "device": "cpu",
        },
    )
    engine = FunASREngine(cfg)

    with patch.dict("sys.modules", {"funasr": None}):
        with pytest.raises(RuntimeError) as exc_info:
            engine._get_model()
        assert "未安装 funasr" in str(exc_info.value)


async def test_funasr_language_and_hotword_passthrough(tmp_path: Path):
    cfg = EngineConfig(
        "funasr",
        {
            "model_name": "iic/SenseVoiceSmall",
            "model_path": str(tmp_path),
            "device": "cpu",
        },
    )
    engine = FunASREngine(cfg)

    mock_model = MagicMock()
    mock_model.generate.return_value = [{"text": "OneASR 测试"}]

    with patch.object(engine, "_get_model", return_value=mock_model):
        await engine.transcribe_file(
            b"fake-pcm-data",
            language="zh-CN",
            prompt="OneASR DuRT",
        )
        gen_kwargs = mock_model.generate.call_args[1]
        assert gen_kwargs["language"] == "zh"
        assert gen_kwargs["hotword"] == "OneASR DuRT"
