"""Masking of inline KAG tags ([r], [ruby text=…], [emb exp=…], …) into
sentinels. Unlike Ren'Py, linebreak codes are REAL here: [r] is masked with
kind `linebreak` and kept in the unit — stripping it is a Stage 5 prompt-
assembly concern, not an extraction concern, or Gate A identity could never
hold (see docs/11)."""

from __future__ import annotations

import re

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


# .scn (KAGEnv) inline codes, grammar taken from a corpus scan of a real
# title (docs/11): %<alnum><args>; where args may contain spaces (font
# names), e.g. %p-1; %p; %fＭＳ ゴシック; %50; — plus \n / \k / \x.
_PERCENT_RE = re.compile(r"%[A-Za-z0-9][^;%\n]{0,40};|%;")
_BACKSLASH_KINDS = {
    "n": PlaceholderKind.LINEBREAK,
    "k": PlaceholderKind.WAIT,
    "x": PlaceholderKind.OPAQUE,
}


def mask(
    text: str, *, scn_codes: bool = False
) -> tuple[str, list[Placeholder]] | None:
    """Mask inline tags. None when the text cannot be masked losslessly.
    With scn_codes=True, also masks the %-code and backslash-code families
    used inside compiled-scenario text."""
    if "⟦" in text or "⟧" in text:
        return None
    out: list[str] = []
    placeholders: list[Placeholder] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if scn_codes and c == "%":
            m = _PERCENT_RE.match(text, i)
            if m is not None:
                idx = len(placeholders)
                placeholders.append(
                    Placeholder(
                        index=idx, raw=m.group(0), kind=PlaceholderKind.OPAQUE
                    )
                )
                out.append(sentinel(idx))
                i = m.end()
                continue
            out.append(c)  # bare % in prose (e.g. １００%) stays text
            i += 1
            continue
        if scn_codes and c == "\\" and i + 1 < n and text[i + 1] in _BACKSLASH_KINDS:
            idx = len(placeholders)
            placeholders.append(
                Placeholder(
                    index=idx,
                    raw=text[i : i + 2],
                    kind=_BACKSLASH_KINDS[text[i + 1]],
                )
            )
            out.append(sentinel(idx))
            i += 2
            continue
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
