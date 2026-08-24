"""Sentinel mask/unmask for the placeholder contract (docs/05).

Sentinel form is ⟦n⟧. docs/05 requires calibrating the glyphs against the real
model before Phase 4; the format is isolated here so that calibration is a
one-line change.
"""

from __future__ import annotations

import re

from tsumugi.core.models import Placeholder

_SENTINEL_RE = re.compile(r"⟦(\d+)⟧")  # ⟦n⟧


def sentinel(index: int) -> str:
    return f"⟦{index}⟧"


def sentinel_indices(text: str) -> list[int]:
    """Every sentinel index in text, in order of appearance."""
    return [int(m.group(1)) for m in _SENTINEL_RE.finditer(text)]


def unmask(text: str, placeholders: list[Placeholder]) -> str:
    """Replace each ⟦n⟧ with its raw markup. Unknown indices are left as-is;
    the placeholder-contract validator is responsible for rejecting those
    before anything reaches an inject path."""
    by_index = {p.index: p.raw for p in placeholders}

    def _sub(m: re.Match[str]) -> str:
        raw = by_index.get(int(m.group(1)))
        return raw if raw is not None else m.group(0)

    return _SENTINEL_RE.sub(_sub, text)


def split_segments(text: str) -> list[tuple[bool, str]]:
    """Split into (is_sentinel, chunk) runs, preserving order and content."""
    out: list[tuple[bool, str]] = []
    pos = 0
    for m in _SENTINEL_RE.finditer(text):
        if m.start() > pos:
            out.append((False, text[pos : m.start()]))
        out.append((True, m.group(0)))
        pos = m.end()
    if pos < len(text):
        out.append((False, text[pos:]))
    return out
