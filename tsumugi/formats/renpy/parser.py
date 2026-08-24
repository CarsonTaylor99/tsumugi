"""Line-based extraction of say statements, narration, and menu choices from
.rpy source. Deliberately conservative: a line we cannot classify with
certainty is skipped, never guessed at (docs/01 Stage 2: misclassified
strings get translated and break the game).

Phase 1 limitations, recorded in docs/11: double-quoted single-line strings
only; no monologue mode; no `voice` statement pairing; `.rpyc` and `.rpa`
inputs are out of scope for the walking skeleton.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from tsumugi.core.models import UnitKind

_IDENT_RE = re.compile(r"^[A-Za-z_]\w*$")

# First-token keywords that mean "this line's strings are not player dialogue".
_KEYWORDS = frozenset(
    "label jump call return scene show hide with play queue stop pause define "
    "default image transform init python screen style translate old new voice "
    "nvl window camera if elif else while for pass at on key text add use "
    "action $ import".split()
)


@dataclass(frozen=True)
class RawSay:
    """One candidate literal: content span is absolute into the decoded file."""

    kind: UnitKind
    speaker: str | None
    raw_content: str  # escaped form, exactly as in the file
    start: int  # abs char offset of content (after the opening quote)


@dataclass(frozen=True)
class _Literal:
    quote_start: int  # index of opening quote within the line
    quote_end: int  # index of closing quote within the line
    raw: str


def _scan_literals(line: str) -> tuple[list[_Literal], int]:
    """Double-quoted literals in a line, honoring backslash escapes and
    stopping at a comment. Returns (literals, comment_cutoff)."""
    literals: list[_Literal] = []
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if c == "#":
            return literals, i
        if c == '"':
            j = i + 1
            while j < n:
                if line[j] == "\\":
                    j += 2
                    continue
                if line[j] == '"':
                    break
                j += 1
            if j >= n:
                return literals, n  # unterminated: not extractable
            literals.append(_Literal(i, j, line[i + 1 : j]))
            i = j + 1
        else:
            i += 1
    return literals, n


def parse_rpy(text: str, *, skip_tl: bool = True) -> list[RawSay]:
    """All extractable literals in one .rpy file, in file order."""
    out: list[RawSay] = []
    menu_indents: list[int] = []
    offset = 0
    in_translate_block = False
    translate_indent = 0

    for line in text.splitlines(keepends=True):
        line_start = offset
        offset += len(line)
        body = line.rstrip("\r\n")
        stripped = body.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(body) - len(body.lstrip())

        # Leave any menu / translate blocks we've dedented out of.
        while menu_indents and indent <= menu_indents[-1]:
            menu_indents.pop()
        if in_translate_block and indent <= translate_indent:
            in_translate_block = False

        first_token = stripped.split(None, 1)[0].rstrip(":")
        if first_token == "translate" and skip_tl:
            in_translate_block = True
            translate_indent = indent
            continue
        if in_translate_block and skip_tl:
            continue
        if first_token == "menu":
            menu_indents.append(indent)
            continue

        literals, cutoff = _scan_literals(body)
        if not literals:
            continue
        prefix = body[indent : literals[0].quote_start].strip()
        suffix = body[literals[-1].quote_end + 1 : cutoff].strip()

        # Menu choice: "text": / "text" if cond:
        if (
            menu_indents
            and len(literals) == 1
            and not prefix
            and (suffix == ":" or (suffix.startswith("if ") and suffix.endswith(":")))
        ):
            out.append(_say(UnitKind.CHOICE, None, literals[0], line_start))
            continue

        if not _suffix_ok(suffix):
            continue

        if len(literals) == 1:
            if not prefix:
                out.append(_say(UnitKind.NARRATION, None, literals[0], line_start))
                continue
            tokens = prefix.split()
            if all(_IDENT_RE.match(t) for t in tokens) and tokens[0] not in _KEYWORDS:
                out.append(_say(UnitKind.DIALOGUE, tokens[0], literals[0], line_start))
            continue

        if len(literals) == 2 and not prefix:
            between = body[literals[0].quote_end + 1 : literals[1].quote_start]
            if between.strip() == "":
                # "Display Name" "dialogue" — speaker is the raw first literal.
                out.append(
                    _say(UnitKind.DIALOGUE, literals[0].raw, literals[1], line_start)
                )
            continue
        # 3+ literals or unclassifiable: skip, never guess.
    return out


def _suffix_ok(suffix: str) -> bool:
    return suffix == "" or suffix == "nointeract" or suffix.startswith("with ")


def _say(kind: UnitKind, speaker: str | None, lit: _Literal, line_start: int) -> RawSay:
    return RawSay(
        kind=kind,
        speaker=speaker,
        raw_content=lit.raw,
        start=line_start + lit.quote_start + 1,
    )


def unescape(raw: str) -> str | None:
    """Canonical unescape. None means the literal uses an escape outside the
    canonical set and cannot be round-tripped byte-identically; the caller
    skips it (left untranslated, loudly)."""
    out: list[str] = []
    i = 0
    n = len(raw)
    table = {'"': '"', "\\": "\\", "n": "\n", "t": "\t"}
    while i < n:
        c = raw[i]
        if c == "\\":
            if i + 1 >= n:
                return None
            sub = table.get(raw[i + 1])
            if sub is None:
                return None
            out.append(sub)
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def escape(text: str) -> str:
    """Canonical escape: the exact inverse of `unescape` on its image."""
    return (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
