"""Term mining, first pass: regex morphology over masked source text.

Katakana runs surface foreign names/terms almost perfectly in VN text;
kanji compounds catch places, organisations, and invented words. This costs
no GPU and no dictionaries. A SudachiPy/fugashi upgrade (docs' stack) slots
in behind the same interface once dictionary licensing is verified —
recorded in docs/11.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

from tsumugi.core.models import TextUnit
from tsumugi.core.sentinels import split_segments

_KATAKANA = re.compile(r"[ァ-ヴー]{2,}")
_KANJI = re.compile(r"[一-鿿]{2,6}")

# High-frequency ordinary words that would drown the list. Small and
# deliberate — ranking does the real filtering.
_STOP = frozenset(
    "自分 今日 明日 昨日 本当 一番 大丈夫 時間 学校 教室 先生 先輩 世界 "
    "気持 言葉 二人 一人 部屋 場所 相手 普通 全部 最初 最後 意味 理由 "
    "問題 感じ 姿 顔 目 手 声 心 頭 体 中 上 下 前 後 話 事 人 何".split()
)


def mine_terms(
    units: Iterable[TextUnit], *, min_count: int = 3
) -> list[tuple[str, int, str, str]]:
    """(term, count, kind, sample_text) ranked by frequency."""
    counts: Counter[tuple[str, str]] = Counter()
    samples: dict[str, str] = {}
    speakers: set[str] = set()
    for u in units:
        if u.speaker:
            speakers.add(u.speaker)
        text = "".join(c for is_s, c in split_segments(u.source_text) if not is_s)
        for m in _KATAKANA.findall(text):
            counts[(m, "katakana")] += 1
            samples.setdefault(m, text[:60])
        for m in _KANJI.findall(text):
            if m not in _STOP:
                counts[(m, "kanji")] += 1
                samples.setdefault(m, text[:60])

    out: list[tuple[str, int, str, str]] = []
    for (term, kind), count in counts.most_common():
        if count < min_count:
            break
        if term in speakers:
            kind = "speaker"
        out.append((term, count, kind, samples.get(term, "")))
    return out
