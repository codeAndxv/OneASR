import pytest

from server.schemas.audio import Segment, WordTimestamp
from server.utils.subtitle_segmenter import SubtitleSegmenter


def test_join_words_cjk_and_english():
    words_zh = [
        WordTimestamp(word="你", start=0.0, end=0.3),
        WordTimestamp(word="好", start=0.3, end=0.6),
        WordTimestamp(word="世界", start=0.6, end=1.0),
    ]
    joined_zh = SubtitleSegmenter._join_words(words_zh)
    assert joined_zh == "你好世界"

    words_en = [
        WordTimestamp(word="hello", start=0.0, end=0.4),
        WordTimestamp(word="world", start=0.4, end=0.8),
    ]
    joined_en = SubtitleSegmenter._join_words(words_en)
    assert joined_en == "hello world"

    words_mixed = [
        WordTimestamp(word="Hello", start=0.0, end=0.4),
        WordTimestamp(word="世界", start=0.4, end=0.8),
    ]
    joined_mixed = SubtitleSegmenter._join_words(words_mixed)
    assert joined_mixed == "Hello 世界"


def test_resegment_on_pause():
    segmenter = SubtitleSegmenter(pause_threshold=0.4, min_duration=0.5)
    words = [
        WordTimestamp(word="第一段开始", start=0.0, end=1.0, probability=0.9),
        WordTimestamp(word="第一段结束", start=1.0, end=2.0, probability=0.95),
        # 停顿 1.5 秒
        WordTimestamp(word="第二段开始", start=3.5, end=4.5, probability=0.88),
        WordTimestamp(word="第二段结束", start=4.5, end=5.5, probability=0.92),
    ]

    segments = segmenter.resegment_from_words(words)
    assert len(segments) == 2
    assert segments[0].text == "第一段开始第一段结束"
    assert segments[0].start == 0.0
    assert segments[0].end == 2.0
    assert segments[0].confidence is not None

    assert segments[1].text == "第二段开始第二段结束"
    assert segments[1].start == 3.5
    assert segments[1].end == 5.5


def test_resegment_on_sentence_end_punctuation():
    segmenter = SubtitleSegmenter(min_duration=0.5)
    words = [
        WordTimestamp(word="你好！", start=0.0, end=1.0),
        WordTimestamp(word="很高兴见到你。", start=1.1, end=2.5),
    ]

    segments = segmenter.resegment_from_words(words)
    assert len(segments) == 2
    assert segments[0].text == "你好！"
    assert segments[1].text == "很高兴见到你。"


def test_resegment_on_max_line_length():
    segmenter = SubtitleSegmenter(max_line_length=10, min_duration=0.1)
    # 创建超长句子
    words = [
        WordTimestamp(word="这是一个非常长非常长的一句话用来测试字符超长自动切分", start=0.0, end=4.0),
        WordTimestamp(word="后续的内容", start=4.1, end=5.0),
    ]
    segments = segmenter.resegment_from_words(words)
    assert len(segments) >= 2


def test_optimize_segments_fallback():
    segmenter = SubtitleSegmenter()
    raw = [
        Segment(id=0, start=0.0, end=2.0, text="  测试文本 1  ", is_endpoint=True),
        Segment(id=1, start=2.5, end=4.0, text="测试文本 2", is_endpoint=True),
    ]
    optimized = segmenter.optimize_segments(raw)
    assert len(optimized) == 2
    assert optimized[0].text == "测试文本 1"
    assert optimized[1].text == "测试文本 2"
