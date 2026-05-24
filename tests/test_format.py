"""测试输出格式转换功能。"""

from app.models.schemas import Segment
from app.utils.format import (
    OutputFormat,
    format_output,
    format_time_srt,
    format_time_vtt,
    to_json,
    to_srt,
    to_text,
    to_tsv,
    to_vtt,
)

# 测试数据
SEGMENTS = [
    Segment(start=0.0, end=2.5, text="你好世界"),
    Segment(start=3.0, end=5.8, text="这是测试"),
]
FULL_TEXT = "你好世界 这是测试"


def test_format_time_srt():
    assert format_time_srt(0) == "00:00:00,000"
    assert format_time_srt(61.5) == "00:01:01,500"
    assert format_time_srt(3661.123) == "01:01:01,123"


def test_format_time_vtt():
    assert format_time_vtt(0) == "00:00:00.000"
    assert format_time_vtt(61.5) == "00:01:01.500"
    assert format_time_vtt(3661.123) == "01:01:01.123"


def test_to_text():
    result = to_text(FULL_TEXT, SEGMENTS)
    assert result == FULL_TEXT


def test_to_srt():
    result = to_srt(FULL_TEXT, SEGMENTS)
    lines = result.strip().split("\n")
    assert lines[0] == "1"
    assert lines[1] == "00:00:00,000 --> 00:00:02,500"
    assert lines[2] == "你好世界"
    assert lines[3] == ""
    assert lines[4] == "2"
    assert "00:00:03,000 --> 00:00:05," in lines[5]  # 浮点精度问题
    assert lines[6] == "这是测试"


def test_to_vtt():
    result = to_vtt(FULL_TEXT, SEGMENTS)
    lines = result.strip().split("\n")
    assert lines[0] == "WEBVTT"
    assert lines[1] == ""
    assert lines[2] == "1"
    assert lines[3] == "00:00:00.000 --> 00:00:02.500"
    assert lines[4] == "你好世界"


def test_to_json():
    import json

    result = to_json(FULL_TEXT, SEGMENTS)
    data = json.loads(result)
    assert data["text"] == FULL_TEXT
    assert len(data["segments"]) == 2
    assert data["segments"][0]["start"] == 0.0
    assert data["segments"][0]["end"] == 2.5
    assert data["segments"][0]["text"] == "你好世界"


def test_to_tsv():
    result = to_tsv(FULL_TEXT, SEGMENTS)
    lines = result.strip().split("\n")
    assert lines[0] == "start\tend\ttext"
    assert lines[1] == "0.000\t2.500\t你好世界"
    assert lines[2] == "3.000\t5.800\t这是测试"


def test_format_output_text():
    result = format_output(FULL_TEXT, SEGMENTS, "text")
    assert result == FULL_TEXT


def test_format_output_srt():
    result = format_output(FULL_TEXT, SEGMENTS, "srt")
    assert "00:00:00,000 --> 00:00:02,500" in result


def test_format_output_enum():
    result = format_output(FULL_TEXT, SEGMENTS, OutputFormat.VTT)
    assert "WEBVTT" in result


def test_format_output_invalid():
    try:
        format_output(FULL_TEXT, SEGMENTS, "invalid")
        assert False, "应该抛出异常"
    except ValueError:
        pass


if __name__ == "__main__":
    test_format_time_srt()
    test_format_time_vtt()
    test_to_text()
    test_to_srt()
    test_to_vtt()
    test_to_json()
    test_to_tsv()
    test_format_output_text()
    test_format_output_srt()
    test_format_output_enum()
    test_format_output_invalid()
    print("所有格式测试通过")
