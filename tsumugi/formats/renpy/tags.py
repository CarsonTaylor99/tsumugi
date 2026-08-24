"""Masking of Ren'Py text tags ({i}, {w=0.5}, ...) and interpolation ([name])
into indexed sentinels, and the reverse. docs/05: the model never sees raw
control codes.

`{{` and `[[` are Ren'Py's escapes for literal braces/brackets; they are
*text*, not markup, and stay in the visible string.
"""

from __future__ import annotations

from tsumugi.core.models import Placeholder, PlaceholderKind
from tsumugi.core.sentinels import sentinel

_RUBY_TAGS = {"rt", "rb", "art"}
_STYLE_TAGS = {
    "i", "b", "s", "u", "plain", "color", "outlinecolor", "size", "font",
    "alpha", "k", "cps", "a", "space", "vspace",
}
_WAIT_TAGS = {"w", "nw", "fast"}
_PAGE_TAGS = {"p", "clear"}


def _tag_kind(body: str) -> PlaceholderKind:
    closing = body.startswith("/")
    base = (body[1:] if closing else body).split("=", 1)[0].strip()
    if base in _RUBY_TAGS:
        return PlaceholderKind.RUBY_CLOSE if closing else PlaceholderKind.RUBY_OPEN
    if base in _STYLE_TAGS:
        return PlaceholderKind.STYLE_CLOSE if closing else PlaceholderKind.STYLE_OPEN
    if closing:
        return PlaceholderKind.OPAQUE
    if base in _WAIT_TAGS:
        return PlaceholderKind.WAIT
    if base in _PAGE_TAGS:
        return PlaceholderKind.PAGEBREAK
    return PlaceholderKind.OPAQUE


def mask(text: str) -> tuple[str, list[Placeholder]] | None:
    """Mask tags and interpolations. Returns (masked, placeholders), or None
    when the text cannot be masked losslessly (unbalanced markup, or source
    that already contains a sentinel glyph)."""
    if "⟦" in text or "⟧" in text:
        return None

    out: list[str] = []
    placeholders: list[Placeholder] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in "{[":
            if i + 1 < n and text[i + 1] == c:  # {{ or [[ -> literal text
                out.append(c + c)
                i += 2
                continue
            closer = "}" if c == "{" else "]"
            end = text.find(closer, i + 1)
            if end < 0:
                return None  # unbalanced markup: refuse rather than guess
            raw = text[i : end + 1]
            kind = (
                _tag_kind(text[i + 1 : end])
                if c == "{"
                else PlaceholderKind.VAR
            )
            idx = len(placeholders)
            placeholders.append(Placeholder(index=idx, raw=raw, kind=kind))
            out.append(sentinel(idx))
            i = end + 1
        else:
            out.append(c)
            i += 1
    return "".join(out), placeholders
