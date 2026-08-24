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
    if count == 0:
        if any(game_dir.glob("*.xp3")):
            typer.echo(
                "0 units but .xp3 archives present — the scripts are still packed. "
                "Run `tsumugi unpack` (or dump an encrypted title with "
                "KirikiriTools) and extract from the unpacked folder.",
                err=True,
            )
        elif any(game_dir.rglob("*.ks")):
            typer.echo(
                "0 translatable units, though .ks scripts are present — they look "
                "like engine/system scripts (all tags, no dialogue). Story scenario "
                "files dump only as the game is played: start a new game and advance "
                "into the story, then re-run extract.",
                err=True,
            )


@app.command()
def analyze(
    game_dir: Path,
    project: Path = typer.Option(Path("project.tsumugi")),
    engine: str = typer.Option("kirikiri"),
) -> None:
    """Stage 3 (no LLM): reading-order graph + term mining into the store."""
    import json as _json

    from tsumugi.analysis.scenegraph import reading_order
    from tsumugi.analysis.terms import mine_terms
    from tsumugi.core.store import ProjectStore

    adapter = next((a for a in all_adapters() if a.name == engine), None)
    if adapter is None:
        typer.echo(f"unknown engine {engine!r}", err=True)
        raise typer.Exit(code=2)
    ws = Workspace(game_dir=game_dir, work_dir=project.parent / "workspace")
    graph = adapter.build_graph(ws)
    ordered = reading_order(graph)

    store = ProjectStore(project)
    try:
        store.replace_scenes(
            [
                (n.file, n.label, n.title, idx, _json.dumps(n.nexts))
                for n, idx in ordered
            ]
        )
        units = [r.unit for r in store.units(limit=1_000_000).rows]
        terms = mine_terms(units)
        store.replace_terms(terms)
        entry_files = [n.file for n, i in ordered if i == 0]
        typer.echo(
            f"scenes: {len(ordered)} across {len({n.file for n, _ in ordered})} files; "
            f"entry: {entry_files[:2]}"
        )
        typer.echo(f"terms mined: {len(terms)}; top 10:")
        for term, count, kind, _ in terms[:10]:
            typer.echo(f"  {count:5}  {term} ({kind})")
    finally:
        store.close()


@app.command(name="bible-map")
def bible_map(
    project: Path = typer.Option(Path("project.tsumugi")),
    model: str | None = typer.Option(None, help="Ollama model; default: first installed."),
    limit: int | None = typer.Option(None, help="Only the first N windows (pilot run)."),
    num_ctx: int = typer.Option(8192),
) -> None:
    """Stage 4 map: per-window observations on the LOCAL model (checkpointed;
    re-running continues)."""
    from tsumugi.bible.mapper import run_map
    from tsumugi.core.store import ProjectStore
    from tsumugi.llm.client import LlmBinding, discover_default_model

    resolved = model or discover_default_model()
    if resolved is None:
        typer.echo("no Ollama model found — is Ollama running?", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"bible.map on {resolved} (num_ctx={num_ctx})")
    store = ProjectStore(project)
    try:
        done, cached, failed = run_map(
            store,
            LlmBinding(model=resolved, num_ctx=num_ctx),
            limit=limit,
        )
    finally:
        store.close()
    typer.echo(f"done {done}, cached {cached}, failed {failed}")
    if failed:
        raise typer.Exit(code=1)


@app.command(name="bible-draft")
def bible_draft(
    project: Path = typer.Option(Path("project.tsumugi")),
    out: Path = typer.Option(Path("bible")),
) -> None:
    """Aggregate observations + mined terms into the draft bible (YAML).
    The draft requires human review before translation (hard rule 5)."""
    from tsumugi.bible.draft import build_draft
    from tsumugi.core.store import ProjectStore

    store = ProjectStore(project)
    try:
        counts = build_draft(store, out)
        store.set_meta(bible_approved="false", bible_dir=str(out))
    finally:
        store.close()
    typer.echo(
        f"draft bible -> {out}  ({counts['cast']} cast cards from "
        f"{counts['windows']} observation windows, {counts['glossary']} glossary rows)"
    )
    typer.echo("review it, then run: tsumugi bible-approve")


@app.command(name="bible-approve")
def bible_approve(project: Path = typer.Option(Path("project.tsumugi"))) -> None:
    """Mark the bible reviewed. Translation refuses to start without this."""
    from tsumugi.core.store import ProjectStore

    store = ProjectStore(project)
    try:
        store.set_meta(bible_approved="true")
    finally:
        store.close()
    typer.echo("bible approved — translation may start (hard rule 5 satisfied)")


@app.command()
def unpack(
    source: Path = typer.Argument(help="A game directory or a single .xp3 file."),
    dest: Path = typer.Option(Path("workspace/unpacked"), help="Extraction target."),
) -> None:
    """Stage 1 for KiriKiri: extract unencrypted XP3 archives.

    Encrypted (per-title cipher) archives are reported with the dump
    workflow instead — Tsumugi never writes into the game directory
    (hard rule 7), so the one-time dump runs from your own copy."""
    from tsumugi.archives.xp3 import Xp3Error, read_index, unpack as xp3_unpack

    archives = [source] if source.is_file() else sorted(source.glob("*.xp3"))
    if not archives:
        typer.echo(f"no .xp3 archives found at {source}", err=True)
        raise typer.Exit(code=1)
    encrypted: list[str] = []
    total = 0
    for arc in archives:
        try:
            index = read_index(arc)
            if index.any_protected:
                encrypted.append(arc.name)
                continue
            n = xp3_unpack(arc, dest / arc.stem)
            typer.echo(f"{arc.name}: {n} files -> {dest / arc.stem}")
            total += n
        except Xp3Error as e:
            encrypted.append(arc.name)
            typer.echo(f"{arc.name}: {e}", err=True)
    if encrypted:
        typer.echo(
            "\nEncrypted archives: " + ", ".join(encrypted) + "\n"
            "One-time dump workflow (KirikiriTools, arcusmaximus):\n"
            "  1. https://github.com/arcusmaximus/KirikiriTools — place its\n"
            "     version.dll next to the game exe (your copy, not managed by\n"
            "     Tsumugi), which dumps files decrypted as the engine loads them\n"
            "     into an 'unencrypted' folder.\n"
            "  2. For .scn-based titles, an appconfig.tjs that force-loads every\n"
            "     scene makes the dump complete in one run —\n"
            "     `tsumugi krkr-dump-script` prints it.\n"
            "  3. Then: tsumugi extract <dump-folder> --project game.tsumugi"
        )
    if total == 0 and not encrypted:
        raise typer.Exit(code=1)


@app.command(name="krkr-dump-script")
def krkr_dump_script() -> None:
    """Print the appconfig.tjs that makes a KirikiriTools dump load every
    scene file, for .scn-based (KAGEnvPlayer) titles."""
    typer.echo(
        'KAGLoadScript("KAGEnvPlayer.tjs");\n'
        'var scn_list = KAGEnvPlayer.internalGetSceneFileList("!scnlist.txt");\n'
        "for (var i = 0; i < scn_list.count; ++i) {\n"
        "  try { Scripts.evalStorage(scn_list[i] + \".scn\"); } catch {}\n"
        "}\n"
        "System.exit();"
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
