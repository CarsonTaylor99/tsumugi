"""Phase 1 CLI: `tsumugi probe` and `tsumugi gates`."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import typer

from tsumugi.core.models import Workspace
from tsumugi.formats import all_adapters, detect

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command()
def probe(game_dir: Path) -> None:
    """Stage 0: detect the engine, with evidence — never a silent guess."""
    probes = detect(game_dir)
    if not probes:
        typer.echo(f"no known engine detected in {game_dir}")
        raise typer.Exit(code=1)
    for p in probes:
        typer.echo(f"{p.engine}  confidence {p.confidence:.2f}")
        for e in p.evidence:
            typer.echo(f"  - {e}")


@app.command()
def gates(
    game_dir: Path,
    engine: str = typer.Option("renpy", help="Adapter to run the gates against."),
    work_dir: Path | None = typer.Option(None, help="Defaults to a temp dir."),
) -> None:
    """Hard rule 2: run Gate A (identity) and Gate B (expansion)."""
    adapter = next((a for a in all_adapters() if a.name == engine), None)
    if adapter is None:
        typer.echo(f"unknown engine {engine!r}", err=True)
        raise typer.Exit(code=2)
    wd = work_dir if work_dir is not None else Path(tempfile.mkdtemp(prefix="tsumugi-"))
    ws = Workspace(game_dir=game_dir, work_dir=wd)
    result = adapter.verify_round_trip(ws)
    for gate in (result.identity, result.expansion):
        status = "PASS" if gate.passed else "FAIL"
        typer.echo(
            f"gate {gate.gate}: {status} "
            f"({gate.files_checked} files, {gate.units_checked} units)"
        )
        for f in gate.failures:
            typer.echo(f"  {f.file}: {f.message}", err=True)
    if not result.passed:
        raise typer.Exit(code=1)


def run() -> None:
    sys.exit(app())
