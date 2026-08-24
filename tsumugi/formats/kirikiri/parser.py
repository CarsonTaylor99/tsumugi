"""Line-based KAG (.ks) scenario parsing.

KAG line grammar (line-start character decides):
  ;comment    *label|title    @command …    anything else = text line

Text lines may open with a 【名前】 or 【名前/表示名】 speaker prefix (the
dominant commercial convention). [iscript]…[endscript] blocks are TJS code
and are skipped entirely.

Encoding is per-file and load-bearing: cp932 and UTF-16LE both round-trip
through Python losslessly for real files, and `detect_encoding` verifies
re-encode == original bytes before any unit is extracted; a file failing
that is skipped loudly (never guessed at).
"""

from __future__ import annotations

from dataclasses import dataclass

from tsumugi.core.models import UnitKind


@dataclass(frozen=True)
class RawKsLine:
    """One text line's translatable span, absolute char offsets."""

    kind: UnitKind
    speaker: str | None
    text: str  # the span exactly as in the file (tags included, not masked)
    start: int  # abs char offset of the span



def detect_encoding(raw: bytes) -> str | None:
    """The file's encoding, verified to round-trip byte-identically."""
    candidates: list[str] = []
    if raw.startswith(b"\xff\xfe"):
        candidates = ["utf-16-le"]  # BOM included in decode/encode round-trip
    elif raw.startswith(b"\xef\xbb\xbf"):
        candidates = ["utf-8-sig"]
    else:
        candidates = ["cp932", "utf-8"]
    for enc in candidates:
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        if text.encode(enc) == raw:
            return enc
    return None


def parse_ks(text: str) -> list[RawKsLine]:
    out: list[RawKsLine] = []
    offset = 0
    in_iscript = False
    for line in text.splitlines(keepends=True):
        line_start = offset
        offset += len(line)
        body = line.rstrip("\r\n")
        # ﻿: a BOM decodes into the first line's text and is not
        # whitespace to str.strip(); treat it as leading junk everywhere.
        stripped = body.strip(" \t﻿")
        if not stripped:
            continue
        first = stripped[0]

        if in_iscript:
            if _is_endscript(stripped):
                in_iscript = False
            continue
        if _is_iscript(stripped):
            in_iscript = True
            continue
        if first in (";", "*", "@"):
            continue  # comment / label / command

        lstripped = body.lstrip(" \t﻿")
        span_start = line_start + (len(body) - len(lstripped))
        span_text = lstripped
        speaker: str | None = None
        kind = UnitKind.NARRATION

        if span_text.startswith("【"):
            close = span_text.find("】")
            if close > 0:
                speaker = span_text[1:close].split("/", 1)[0]
                kind = UnitKind.DIALOGUE
                span_start += close + 1
                span_text = span_text[close + 1 :]

        if not span_text:
            continue
        out.append(
            RawKsLine(kind=kind, speaker=speaker, text=span_text, start=span_start)
        )
    return out


def _is_iscript(stripped: str) -> bool:
    low = stripped.lower()
    return low.startswith(("[iscript]", "@iscript"))


def _is_endscript(stripped: str) -> bool:
    low = stripped.lower()
    return low.startswith(("[endscript]", "@endscript"))
