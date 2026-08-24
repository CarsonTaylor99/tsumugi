"""Ren'Py EngineAdapter.

Round-trip strategy (the Gate A resolution recorded in docs/11): extraction
asserts, per literal, that canonical-escape(unescape(raw)) == raw and that
tag masking is lossless. Any literal failing either check is skipped —
loudly, never guessed at. Inject is then an exact span rewrite, so Gate A
byte-identity genuinely exercises the encode path rather than passing by
copying bytes around the edit.

Production injection for Ren'Py will prefer the engine's tl/ framework;
the span-rewrite path is what proves the generic machinery (and is also a
legitimate patch path for games shipping .rpy source).
"""

from __future__ import annotations

import hashlib
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Iterator

from tsumugi.core.models import (
    EngineProbe,
    EngineTextCaps,
    RoundTripResult,
    ScriptGraph,
    TextUnit,
    Workspace,
)
from tsumugi.core.sentinels import unmask
from tsumugi.formats.renpy.parser import escape, parse_rpy, unescape
from tsumugi.formats.renpy.tags import mask
from tsumugi.qa.gates import run_gates
from tsumugi.qa.placeholders import check_placeholder_contract


class RenpyAdapter:
    name = "renpy"
    caps = EngineTextCaps(
        source_encoding="utf-8",
        renders_utf8=True,
        break_code="\n",
        max_lines=None,
        ruby_syntax="{rb}/{rt}",
        proportional_fonts=True,
        var_interpolation=True,
    )

    def probe(self, game_dir: Path) -> EngineProbe | None:
        evidence: list[str] = []
        confidence = 0.0
        game = game_dir / "game"
        if game.is_dir():
            evidence.append("game/ directory present")
            confidence += 0.3
        root = game if game.is_dir() else game_dir
        if any(root.rglob("*.rpy")) or any(root.rglob("*.rpyc")):
            evidence.append(".rpy/.rpyc scripts present")
            confidence += 0.4
        if any(root.rglob("*.rpa")):
            evidence.append(".rpa archives present")
            confidence += 0.3
        if (game_dir / "renpy").is_dir():
            evidence.append("renpy/ runtime directory present")
            confidence += 0.3
        if not evidence:
            return None
        return EngineProbe(
            engine=self.name, confidence=min(confidence, 0.99), evidence=evidence
        )

    def _script_root(self, base: Path) -> Path:
        game = base / "game"
        return game if game.is_dir() else base

    def _script_files(self, base: Path) -> list[Path]:
        root = self._script_root(base)
        return sorted(
            p for p in root.rglob("*.rpy") if "tl" not in p.relative_to(root).parts
        )

    def extract(self, ws: Workspace) -> Iterator[TextUnit]:
        ordinal = 0
        for path in self._script_files(ws.game_dir):
            rel = path.relative_to(ws.game_dir).as_posix()
            text = path.read_bytes().decode("utf-8")
            for raw in parse_rpy(text):
                ordinal += 1
                unescaped = unescape(raw.raw_content)
                if unescaped is None:
                    _skip(rel, raw.start, "non-canonical escape sequence")
                    continue
                masked_result = mask(unescaped)
                if masked_result is None:
                    _skip(rel, raw.start, "unbalanced markup or sentinel glyph")
                    continue
                masked, placeholders = masked_result
                digest = hashlib.sha256(masked.encode("utf-8")).hexdigest()
                yield TextUnit(
                    id=f"{rel}:{raw.start}:{digest[:8]}",
                    source_text=masked,
                    placeholders=placeholders,
                    speaker=raw.speaker,
                    kind=raw.kind,
                    file=rel,
                    offset=raw.start,
                    length=len(raw.raw_content),
                    ordinal=ordinal,
                    source_hash=digest,
                )

    def inject(self, ws: Workspace, units: Iterable[TextUnit]) -> None:
        by_file: dict[str, list[TextUnit]] = defaultdict(list)
        for u in units:
            by_file[u.file].append(u)
        for rel, file_units in by_file.items():
            src = (ws.game_dir / rel).read_bytes().decode("utf-8")
            for u in sorted(file_units, key=lambda u: u.offset, reverse=True):
                text = u.target_text if u.target_text is not None else u.source_text
                problems = check_placeholder_contract(u, text)
                if problems:
                    raise ValueError(
                        f"{rel} unit {u.ordinal}: contract violated: {problems}"
                    )
                new_raw = escape(unmask(text, u.placeholders))
                src = src[: u.offset] + new_raw + src[u.offset + u.length :]
            out_path = ws.patched_dir() / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(src.encode("utf-8"))

    def build_graph(self, ws: Workspace) -> ScriptGraph:
        # Ren'Py label/jump graph is future Phase 7 work; empty is honest.
        return ScriptGraph()

    def verify_round_trip(self, ws: Workspace) -> RoundTripResult:
        return run_gates(self, ws)


def _skip(rel: str, offset: int, reason: str) -> None:
    # One terse line per skip (CLAUDE.md: terse failures, with values).
    print(f"skip {rel}@{offset}: {reason}", file=sys.stderr)
