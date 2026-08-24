"""The two round-trip gates (hard rule 2), written once for every adapter.

Gate A — identity: extract -> inject unchanged -> byte-identical files.
Gate B — expansion: extract -> inject ~2x ASCII filler -> re-extract ->
same units, same placeholders, expanded text intact.

Failure messages carry offsets and byte values: `expected 0x40 at offset 12,
got 0x44` costs one read; `assert failed` costs a debugging session.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from tsumugi.core.adapter import EngineAdapter
from tsumugi.core.models import (
    GateFailure,
    GateResult,
    RoundTripResult,
    TextUnit,
    Workspace,
)
from tsumugi.core.sentinels import split_segments

_FILLER = "expansion gate filler text "


def expansion_text(masked: str, factor: float = 2.0) -> str:
    """ASCII filler at ~factor x length per text segment, sentinels kept
    in place. Matches the docs/10 Gate B definition."""
    out: list[str] = []
    for is_sentinel, chunk in split_segments(masked):
        if is_sentinel:
            out.append(chunk)
        else:
            target_len = max(1, round(len(chunk) * factor))
            filler = (_FILLER * (target_len // len(_FILLER) + 1))[:target_len]
            out.append(filler)
    return "".join(out)


def _first_byte_diff(a: bytes, b: bytes) -> str:
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            ctx_a = a[max(0, i - 8) : i + 8].hex(" ")
            ctx_b = b[max(0, i - 8) : i + 8].hex(" ")
            return (
                f"byte {i}: expected 0x{a[i]:02x}, got 0x{b[i]:02x}; "
                f"context expected [{ctx_a}] got [{ctx_b}]"
            )
    return f"length differs: expected {len(a)} bytes, got {len(b)}"


def run_identity_gate(adapter: EngineAdapter, ws: Workspace) -> GateResult:
    units = list(adapter.extract(ws))
    for u in units:
        u.target_text = None  # identity path
    _clean(ws.patched_dir())
    adapter.inject(ws, units)

    failures: list[GateFailure] = []
    files = sorted({u.file for u in units})
    for rel in files:
        original = (ws.game_dir / rel).read_bytes()
        patched_path = ws.patched_dir() / rel
        if not patched_path.exists():
            failures.append(GateFailure(file=rel, message="inject wrote no file"))
            continue
        patched = patched_path.read_bytes()
        if original != patched:
            failures.append(
                GateFailure(file=rel, message=_first_byte_diff(original, patched))
            )
    return GateResult(
        gate="identity",
        files_checked=len(files),
        units_checked=len(units),
        failures=failures,
    )


def run_expansion_gate(adapter: EngineAdapter, ws: Workspace) -> GateResult:
    units = list(adapter.extract(ws))
    for u in units:
        u.target_text = expansion_text(u.source_text)
    _clean(ws.patched_dir())
    adapter.inject(ws, units)

    failures: list[GateFailure] = []
    reread_ws = Workspace(
        game_dir=ws.patched_dir(), work_dir=ws.work_dir / "expansion-reread"
    )
    reread = list(adapter.extract(reread_ws))

    if len(reread) != len(units):
        failures.append(
            GateFailure(
                file="*",
                message=f"unit count changed: {len(units)} before, {len(reread)} after",
            )
        )
    else:
        for before, after in zip(units, reread):
            failures.extend(_compare_expanded(before, after))

    return GateResult(
        gate="expansion",
        files_checked=len({u.file for u in units}),
        units_checked=len(units),
        failures=failures,
    )


def _compare_expanded(before: TextUnit, after: TextUnit) -> list[GateFailure]:
    out: list[GateFailure] = []
    expected_text = before.target_text
    if expected_text is not None and after.source_text != expected_text:
        out.append(
            GateFailure(
                file=before.file,
                message=(
                    f"unit {before.ordinal}: text mangled after expansion; "
                    f"expected {expected_text[:40]!r}..., got {after.source_text[:40]!r}..."
                ),
            )
        )
    b_ph = sorted((p.index, p.raw) for p in before.placeholders)
    a_ph = sorted((p.index, p.raw) for p in after.placeholders)
    if b_ph != a_ph:
        out.append(
            GateFailure(
                file=before.file,
                message=f"unit {before.ordinal}: placeholders {b_ph} became {a_ph}",
            )
        )
    return out


def run_gates(adapter: EngineAdapter, ws: Workspace) -> RoundTripResult:
    return RoundTripResult(
        identity=run_identity_gate(adapter, ws),
        expansion=run_expansion_gate(adapter, ws),
    )


def _clean(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
