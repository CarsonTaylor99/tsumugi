"""Project store: insert, query, filters, dedupe counts."""

from pathlib import Path

from tsumugi.core.models import Workspace
from tsumugi.core.store import ProjectStore
from tsumugi.formats.renpy.adapter import RenpyAdapter

FIXTURE = Path(__file__).parent / "fixtures" / "renpy_tier0"


def _loaded_store(tmp_path: Path) -> ProjectStore:
    store = ProjectStore(tmp_path / "p.tsumugi")
    ws = Workspace(game_dir=FIXTURE, work_dir=tmp_path / "ws")
    count = store.replace_units(RenpyAdapter().extract(ws))
    assert count >= 15, f"only {count} units loaded from Tier 0"
    return store

def test_units_roundtrip_through_sqlite(tmp_path: Path) -> None:
    store = _loaded_store(tmp_path)
    ws = Workspace(game_dir=FIXTURE, work_dir=tmp_path / "ws2")
    direct = list(RenpyAdapter().extract(ws))
    page = store.units(limit=500)
    assert page.total == len(direct)
    stored = {r.unit.id: r.unit for r in page.rows}
    for u in direct:
        assert stored[u.id] == u, f"unit {u.id} changed through the store"
    assert all(r.status == "pending" for r in page.rows)
    store.close()


def test_filters(tmp_path: Path) -> None:
    store = _loaded_store(tmp_path)
    by_speaker = store.units(speaker="e", limit=500)
    assert by_speaker.total > 0
    assert all(r.unit.speaker == "e" for r in by_speaker.rows)

    by_kind = store.units(kind="choice", limit=500)
    assert by_kind.total == 4, f"expected 4 choices in Tier 0, got {by_kind.total}"

    search = store.units(q="夕日")
    assert search.total == 1, f"expected 1 hit for 夕日, got {search.total}"

    paged = store.units(limit=5, offset=0)
    assert len(paged.rows) == 5 and paged.total > 5
    store.close()


def test_stats_and_meta(tmp_path: Path) -> None:
    store = _loaded_store(tmp_path)
    store.set_meta(game_dir=str(FIXTURE), engine="renpy")
    assert store.meta()["engine"] == "renpy"
    stats = store.stats()
    assert stats.total_units == store.units(limit=1).total
    assert len(stats.files) == 2, stats.files
    assert "e" in stats.speakers and "m" in stats.speakers, stats.speakers
    assert stats.by_kind.get("choice") == 4, stats.by_kind
    store.close()


def test_replace_units_is_idempotent(tmp_path: Path) -> None:
    store = _loaded_store(tmp_path)
    before = store.units(limit=1).total
    ws = Workspace(game_dir=FIXTURE, work_dir=tmp_path / "ws3")
    store.replace_units(RenpyAdapter().extract(ws))
    assert store.units(limit=1).total == before
    store.close()
