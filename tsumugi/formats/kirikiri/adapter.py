"""KiriKiri EngineAdapter.

Operates on loose .ks files — either a dumped/unpacked workspace (encrypted
titles, via GARbro/KrkrExtract) or files Tsumugi's own XP3 reader extracted
(unencrypted archives). Round-trip strategy mirrors Ren'Py: per-file the
encoding is verified to re-encode byte-identically, per-line the tag masking
is verified lossless, and inject is an exact span rewrite — so Gate A tests
the writer for real.
"""

from __future__ import annotations

import hashlib
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Iterator

from tsumugi.archives.xp3 import Xp3Error, read_index
from tsumugi.core.models import (
    EngineProbe,
    EngineTextCaps,
    RoundTripResult,
    TextUnit,
    Workspace,
)
from tsumugi.core.sentinels import split_segments, unmask
from tsumugi.formats.kirikiri.parser import detect_encoding, parse_ks
from tsumugi.formats.kirikiri.tags import mask
from tsumugi.qa.gates import run_gates
from tsumugi.qa.placeholders import check_placeholder_contract


class KirikiriAdapter:
    name = "kirikiri"
    caps = EngineTextCaps(
        source_encoding="cp932",  # per-file in practice; recorded per unit's file
        renders_utf8=False,
        break_code="[r]",
        max_lines=3,
        ruby_syntax="[ruby text=…]",
        proportional_fonts=False,
        var_interpolation=True,
    )

    def probe(self, game_dir: Path) -> EngineProbe | None:
        evidence: list[str] = []
        confidence = 0.0
        xp3s = sorted(game_dir.glob("*.xp3"))
        if xp3s:
            evidence.append(f"{len(xp3s)} .xp3 archives (XP3 = KiriKiri container)")
            confidence += 0.6
            protected = 0
            for p in xp3s[:4]:
                try:
                    if read_index(p).any_protected:
                        protected += 1
                except Xp3Error:
                    protected += 1
            if protected:
                evidence.append(
                    f"{protected} archive(s) use per-title encryption — dump once "
                    "with GARbro or KrkrExtract, then extract from the dump"
                )
        if any(game_dir.rglob("*.ks")):
            evidence.append("loose .ks scenario files present")
            confidence += 0.4
        if (game_dir / "plugin").is_dir():
            evidence.append("plugin/ directory present")
            confidence += 0.1
        if not evidence:
            return None
        return EngineProbe(
            engine=self.name, confidence=min(confidence, 0.99), evidence=evidence
        )

    def _script_files(self, base: Path) -> list[Path]:
        return sorted(base.rglob("*.ks"))

    def extract(self, ws: Workspace) -> Iterator[TextUnit]:
        ordinal = 0
        for path in self._script_files(ws.game_dir):
            rel = path.relative_to(ws.game_dir).as_posix()
            raw = path.read_bytes()
            enc = detect_encoding(raw)
            if enc is None:
                _skip(rel, 0, "encoding does not round-trip byte-identically")
                continue
            text = raw.decode(enc)
            for line in parse_ks(text):
                ordinal += 1
                masked_result = mask(line.text)
                if masked_result is None:
                    _skip(rel, line.start, "unterminated tag or sentinel glyph")
                    continue
                masked, placeholders = masked_result
                if not _has_visible_text(masked):
                    continue  # tags-only line: nothing to translate
                digest = hashlib.sha256(masked.encode("utf-8")).hexdigest()
                yield TextUnit(
                    id=f"{rel}:{line.start}:{digest[:8]}",
                    source_text=masked,
                    placeholders=placeholders,
                    speaker=line.speaker,
                    kind=line.kind,
                    file=rel,
                    offset=line.start,
                    length=len(line.text),
                    ordinal=ordinal,
                    source_hash=digest,
                    preserve_breaks=False,
                )

    def inject(self, ws: Workspace, units: Iterable[TextUnit]) -> None:
        by_file: dict[str, list[TextUnit]] = defaultdict(list)
        for u in units:
            by_file[u.file].append(u)
        for rel, file_units in by_file.items():
            raw = (ws.game_dir / rel).read_bytes()
            enc = detect_encoding(raw)
            if enc is None:
                raise ValueError(f"{rel}: encoding no longer round-trips")
            src = raw.decode(enc)
            for u in sorted(file_units, key=lambda u: u.offset, reverse=True):
                text = u.target_text if u.target_text is not None else u.source_text
                problems = check_placeholder_contract(u, text)
                bare = "".join(c for is_s, c in split_segments(text) if not is_s)
                if "[" in bare.replace("[[", "") or "]" in bare.replace("]]", ""):
                    problems.append("raw bracket outside a sentinel (would parse as a tag)")
                if problems:
                    raise ValueError(
                        f"{rel} unit {u.ordinal}: contract violated: {problems}"
                    )
                new_raw = unmask(text, u.placeholders)
                src = src[: u.offset] + new_raw + src[u.offset + u.length :]
            out_path = ws.patched_dir() / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(src.encode(enc))

    def verify_round_trip(self, ws: Workspace) -> RoundTripResult:
        return run_gates(self, ws)


def _has_visible_text(masked: str) -> bool:
    return any(chunk.strip() for is_s, chunk in split_segments(masked) if not is_s)


def _skip(rel: str, offset: int, reason: str) -> None:
    print(f"skip {rel}@{offset}: {reason}", file=sys.stderr)
