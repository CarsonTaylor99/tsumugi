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


@app.command()
def extract(
    game_dir: Path,
    project: Path = typer.Option(
        Path("project.tsumugi"), help="Project store to create or refresh."
    ),
) -> None:
    """Stages 0-2: detect, extract, and load the project store."""
    from tsumugi.core.store import ProjectStore

    probes = detect(game_dir)
    if not probes:
        typer.echo(f"no known engine detected in {game_dir}", err=True)
        raise typer.Exit(code=1)
    top = probes[0]
    typer.echo(f"engine: {top.engine} (confidence {top.confidence:.2f})")
    adapter = next(a for a in all_adapters() if a.name == top.engine)

    ws = Workspace(game_dir=game_dir, work_dir=project.parent / "workspace")
    store = ProjectStore(project)
    try:
        count = store.replace_units(adapter.extract(ws))
        store.set_meta(game_dir=str(game_dir), engine=top.engine)
        stats = store.stats()
    finally:
        store.close()
    typer.echo(
        f"{count} units from {len(stats.files)} files -> {project}  "
        f"({stats.duplicate_units} units in {stats.duplicate_groups} duplicate groups)"
    )


@app.command()
def serve(
    project: Path = typer.Argument(Path("project.tsumugi")),
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8788),
) -> None:
    """Open the read-only workbench over a project store."""
    import uvicorn

    from tsumugi.studio.app import create_app

    if not project.exists():
        typer.echo(f"{project} does not exist — run `tsumugi extract` first", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"Tsumugi Studio on http://{host}:{port}")
    uvicorn.run(create_app(project), host=host, port=port, log_level="warning")


def run() -> None:
    sys.exit(app())
