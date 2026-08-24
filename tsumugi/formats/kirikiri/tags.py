"""Masking of inline KAG tags ([r], [ruby text=…], [emb exp=…], …) into
sentinels. Unlike Ren'Py, linebreak codes are REAL here: [r] is masked with
kind `linebreak` and kept in the unit — stripping it is a Stage 5 prompt-
assembly concern, not an extraction concern, or Gate A identity could never
hold (see docs/11)."""

from __future__ import annotations

from tsumugi.core.models import Placeholder, PlaceholderKind
from tsumugi.core.sentinels import sentinel

_KIND_BY_NAME: dict[str, PlaceholderKind] = {
    "r": PlaceholderKind.LINEBREAK,
    "p": PlaceholderKind.PAGEBREAK,
    "np": PlaceholderKind.PAGEBREAK,
    "pg": PlaceholderKind.PAGEBREAK,
    "cm": PlaceholderKind.PAGEBREAK,
    "ct": PlaceholderKind.PAGEBREAK,
    "l": PlaceholderKind.WAIT,
    "w": PlaceholderKind.WAIT,
    "wait": PlaceholderKind.WAIT,
    "ruby": PlaceholderKind.RUBY_OPEN,  # KAG ruby has no close tag
    "emb": PlaceholderKind.VAR,
    "voice": PlaceholderKind.VOICE,
    "playse": PlaceholderKind.SE,
    "se": PlaceholderKind.SE,
}


def _tag_name(body: str) -> str:
    name = body.strip().split(None, 1)[0] if body.strip() else ""
    return name.lower()


def find_tag_end(text: str, start: int) -> int | None:
    """Index just past the ']' closing the tag opened at text[start] == '[',
    honoring quoted attribute values. None if unterminated."""
    i = start + 1
    n = len(text)
    quote: str | None = None
    while i < n:
        c = text[i]
        if quote is not None:
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c == "]":
            return i + 1
        i += 1
    return None


def mask(text: str) -> tuple[str, list[Placeholder]] | None:
    """Mask inline tags. None when the text cannot be masked losslessly."""
    if "⟦" in text or "⟧" in text:
        return None
    out: list[str] = []
    placeholders: list[Placeholder] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "[":
            if i + 1 < n and text[i + 1] == "[":  # [[ is a literal bracket
                out.append("[[")
                i += 2
                continue
            end = find_tag_end(text, i)
            if end is None:
                return None  # unterminated tag: refuse rather than guess
            raw = text[i:end]
            kind = _KIND_BY_NAME.get(_tag_name(raw[1:-1]), PlaceholderKind.OPAQUE)
            idx = len(placeholders)
            placeholders.append(Placeholder(index=idx, raw=raw, kind=kind))
            out.append(sentinel(idx))
            i = end
        else:
            out.append(c)
            i += 1
    return "".join(out), placeholders
