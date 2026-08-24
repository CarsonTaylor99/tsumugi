"""Read-only Phase 2 workbench API over one project store."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

from tsumugi.core.store import ProjectStore, StoreStats, UnitRow

_HTML = Path(__file__).parent / "workbench.html"


def _row_json(r: UnitRow) -> dict[str, object]:
    u = r.unit
    return {
        "id": u.id,
        "file": u.file,
        "ordinal": u.ordinal,
        "speaker": u.speaker,
        "kind": u.kind.value,
        "source_text": u.source_text,
        "target_text": u.target_text,
        "placeholders": len(u.placeholders),
        "status": r.status,
        "dup_count": r.dup_count,
    }


def create_app(store_path: Path) -> FastAPI:
    app = FastAPI(title="Tsumugi Studio", docs_url=None, redoc_url=None)

    def store() -> ProjectStore:
        # One connection per request: sqlite3 objects are thread-bound and
        # uvicorn may serve requests from different threads.
        return ProjectStore(store_path)

    def _index() -> str:
        return _HTML.read_text(encoding="utf-8")

    def _meta() -> dict[str, str]:
        s = store()
        try:
            return s.meta()
        finally:
            s.close()

    def _stats() -> StoreStats:
        s = store()
        try:
            return s.stats()
        finally:
            s.close()

    def _units(
        file: str | None = None,
        speaker: str | None = None,
        kind: str | None = None,
        status: str | None = None,
        q: str | None = None,
        dupes_only: bool = False,
        page: int = Query(default=1, ge=1),
        per_page: int = Query(default=100, ge=1, le=500),
    ) -> dict[str, object]:
        s = store()
        try:
            result = s.units(
                file=file,
                speaker=speaker,
                kind=kind,
                status=status,
                q=q,
                dupes_only=dupes_only,
                limit=per_page,
                offset=(page - 1) * per_page,
            )
        finally:
            s.close()
        return {
            "total": result.total,
            "page": page,
            "per_page": per_page,
            "units": [_row_json(r) for r in result.rows],
        }

    # Registered by call rather than decorator: passing the function as an
    # argument is what marks it used under pyright --strict.
    app.get("/", response_class=HTMLResponse)(_index)
    app.get("/api/meta")(_meta)
    app.get("/api/stats")(_stats)
    app.get("/api/units")(_units)
    return app
