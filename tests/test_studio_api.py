"""Workbench API over a real extracted store."""

# starlette 0.50+ imports httpx lazily behind a deprecation shim, which erases
# TestClient's types. Suppress unknown-type checks for this file only; the
# assertions still verify the payloads.
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from pathlib import Path

from fastapi.testclient import TestClient

from tsumugi.core.models import Workspace
from tsumugi.core.store import ProjectStore
from tsumugi.formats.renpy.adapter import RenpyAdapter
from tsumugi.studio.app import create_app

FIXTURE = Path(__file__).parent / "fixtures" / "renpy_tier0"


def _client(tmp_path: Path) -> TestClient:
    store_path = tmp_path / "p.tsumugi"
    store = ProjectStore(store_path)
    ws = Workspace(game_dir=FIXTURE, work_dir=tmp_path / "ws")
    store.replace_units(RenpyAdapter().extract(ws))
    store.set_meta(game_dir=str(FIXTURE), engine="renpy")
    store.close()
    return TestClient(create_app(store_path))


def test_index_serves_workbench(tmp_path: Path) -> None:
    r = _client(tmp_path).get("/")
    assert r.status_code == 200
    assert "Tsumugi Studio" in r.text


def test_units_endpoint(tmp_path: Path) -> None:
    c = _client(tmp_path)
    data = c.get("/api/units", params={"per_page": 10}).json()
    assert data["total"] >= 15 and len(data["units"]) == 10
    first = data["units"][0]
    for key in ("id", "file", "speaker", "kind", "source_text", "status", "dup_count"):
        assert key in first, f"missing {key} in {sorted(first)}"

    filtered = c.get("/api/units", params={"speaker": "e"}).json()
    assert filtered["total"] > 0
    assert all(u["speaker"] == "e" for u in filtered["units"])


def test_stats_and_meta_endpoints(tmp_path: Path) -> None:
    c = _client(tmp_path)
    stats = c.get("/api/stats").json()
    assert stats["total_units"] >= 15
    assert stats["by_kind"]["choice"] == 4
    assert c.get("/api/meta").json()["engine"] == "renpy"
