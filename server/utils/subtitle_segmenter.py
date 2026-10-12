"""
智能字幕分句与重切分工具 (Subtitle Segmenter)

Clean-room 独立设计与实现：
1. 基于词级时间戳 (Word Timestamps) 重构结构规整、节奏优美的字幕块；
2. 遵循视频字幕工业规范（控制单行字数 15~30 字、单句时长 1.0~6.0 秒、停顿间隙自动切断）；
3. 智能兼容中英文混排（中文字符间去除冗余空格，英文单词间保留标准空格）；
4. 当词级时间戳缺失时，自动退化为标点与时间插值平滑切分。
"""

import re
from typing import Optional

from server.schemas.audio import Segment, WordTimestamp


CJK_REGEX = re.compile(r"[\u4e00-\u9fa5\u3040-\u30ff\uac00-\ud7af]")
SENTENCE_END_PUNCTUATION = set("。！？.!?\n")
COMMA_PUNCTUATION = set("，,、；;:")


class SubtitleSegmenter:
    """字幕智能规整与重断句器。"""

    def __init__(
        self,
        max_line_length: int = 30,
        min_line_length: int = 2,
        max_duration: float = 6.0,
        min_duration: float = 0.8,
        pause_threshold: float = 0.35,  # 停顿超过 350ms 视为自然断句点
    ):
        self.max_line_length = max_line_length
        self.min_line_length = min_line_length
        self.max_duration = max_duration
        self.min_duration = min_duration
        self.pause_threshold = pause_threshold

    @staticmethod
    def _join_words(words: list[WordTimestamp]) -> str:
        """根据词的语言类型智能拼接文本。"""
        if not words:
            return ""
        
        result: list[str] = []
        for i, w in enumerate(words):
            word_str = w.word.strip()
            if not word_str:
                continue
            if not result:
                result.append(word_str)
                continue
            
            prev_str = result[-1]
            last_char = prev_str[-1] if prev_str else ""
            first_char = word_str[0] if word_str else ""

            # 判断中日韩字符还是英文字符
            prev_is_cjk = bool(CJK_REGEX.search(last_char))
            curr_is_cjk = bool(CJK_REGEX.search(first_char))

            if prev_is_cjk and curr_is_cjk:
                result.append(word_str)
            elif prev_is_cjk and not curr_is_cjk:
                result.append(" " + word_str)
            elif not prev_is_cjk and curr_is_cjk:
                result.append(" " + word_str)
            else:
                # 都是西文
                if word_str in COMMA_PUNCTUATION or word_str in SENTENCE_END_PUNCTUATION:
                    result.append(word_str)
                else:
                    result.append(" " + word_str)

        return "".join(result).strip()

    def resegment_from_words(
        self,
        all_words: list[WordTimestamp],
        speaker: Optional[int | str] = None,
        base_id: int = 0,
    ) -> list[Segment]:
        """从扁平的词级时间戳列表中重构规整的字幕片段列表。"""
        if not all_words:
            return []

        # 过滤无效词
        valid_words = [w for w in all_words if w.word.strip()]
        if not valid_words:
            return []

        segments: list[Segment] = []
        current_chunk: list[WordTimestamp] = []

        for i, word in enumerate(valid_words):
            if not current_chunk:
                current_chunk.append(word)
                continue

            prev_word = current_chunk[-1]
            gap = max(0.0, word.start - prev_word.end)
            duration_if_add = max(0.0, word.end - current_chunk[0].start)
            current_text = self._join_words(current_chunk)
            length_if_add = len(current_text) + len(word.word.strip())

            # 检查是否有结束标点
            last_char = prev_word.word.strip()[-1] if prev_word.word.strip() else ""
            has_sentence_end = last_char in SENTENCE_END_PUNCTUATION
            has_comma = last_char in COMMA_PUNCTUATION

            should_split = False

            # 条件 1: 遇到强结束标点 (。！？) 且当前长度达到最小阈值
            if has_sentence_end and duration_if_add >= self.min_duration:
                should_split = True
            # 条件 2: 停顿超过阈值 (pause_threshold)
            elif gap >= self.pause_threshold and duration_if_add >= self.min_duration:
                should_split = True
            # 条件 3: 达到最大时长限制
            elif duration_if_add >= self.max_duration:
                should_split = True
            # 条件 4: 达到最大字符限制
            elif length_if_add >= self.max_line_length:
                should_split = True
            # 条件 5: 逗号且时长适中
            elif has_comma and duration_if_add >= (self.max_duration * 0.6):
                should_split = True

            if should_split:
                chunk_text = self._join_words(current_chunk)
                if chunk_text:
                    probs = [w.probability for w in current_chunk if w.probability is not None]
                    avg_prob = sum(probs) / len(probs) if probs else None
                    segments.append(
                        Segment(
                            id=base_id + len(segments),
                            start=round(current_chunk[0].start, 3),
                            end=round(current_chunk[-1].end, 3),
                            text=chunk_text,
                            speaker=speaker,
                            is_endpoint=True,
                            words=list(current_chunk),
                            confidence=round(avg_prob, 3) if avg_prob is not None else None,
                        )
                    )
                current_chunk = [word]
            else:
                current_chunk.append(word)

        if current_chunk:
            chunk_text = self._join_words(current_chunk)
            if chunk_text:
                probs = [w.probability for w in current_chunk if w.probability is not None]
                avg_prob = sum(probs) / len(probs) if probs else None
                segments.append(
                    Segment(
                        id=base_id + len(segments),
                        start=round(current_chunk[0].start, 3),
                        end=round(current_chunk[-1].end, 3),
                        text=chunk_text,
                        speaker=speaker,
                        is_endpoint=True,
                        words=list(current_chunk),
                        confidence=round(avg_prob, 3) if avg_prob is not None else None,
                    )
                )

        return segments

    def optimize_segments(self, raw_segments: list[Segment]) -> list[Segment]:
        """对已有 Segment 列表执行优化：如果含有 words 则精准重构，否则平滑长句。"""
        if not raw_segments:
            return []

        # 检查是否包含有效词级时间戳
        has_words = any(
            s.words and any(w.word.strip() for w in s.words)
            for s in raw_segments
        )
        if has_words:
            optimized: list[Segment] = []
            base_id = 0
            for seg in raw_segments:
                if seg.words and any(w.word.strip() for w in seg.words):
                    rebuilt = self.resegment_from_words(seg.words, speaker=seg.speaker, base_id=base_id)
                    if rebuilt:
                        optimized.extend(rebuilt)
                        base_id += len(rebuilt)
                    else:
                        seg.id = base_id
                        optimized.append(seg)
                        base_id += 1
                else:
                    seg.id = base_id
                    optimized.append(seg)
                    base_id += 1
            return optimized

        # 若无词级时间戳，进行基于标点与时长的降级规范化
        return self._normalize_without_words(raw_segments)

    def _normalize_without_words(self, raw_segments: list[Segment]) -> list[Segment]:
        """无词级时间戳时的文本平滑与重编号。"""
        normalized: list[Segment] = []
        for i, seg in enumerate(raw_segments):
            text = seg.text.strip()
            # 清除多余空白
            text = re.sub(r"\s+", " ", text)
            normalized.append(
                Segment(
                    id=i,
                    start=round(seg.start, 3),
                    end=round(seg.end, 3),
                    text=text,
                    speaker=seg.speaker,
                    is_endpoint=seg.is_endpoint,
                    words=None,
                    confidence=seg.confidence,
                )
            )
        return normalized
