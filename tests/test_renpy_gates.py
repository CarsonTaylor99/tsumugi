"""Hard rule 2 over the Tier 0 corpus: both gates, both required."""

from pathlib import Path

from tsumugi.core.models import Workspace
from tsumugi.formats.renpy.adapter import RenpyAdapter

FIXTURE = Path(__file__).parent / "fixtures" / "renpy_tier0"


def _failures(gate_failures: list[object]) -> str:
    return "\n".join(str(f) for f in gate_failures)


def test_gate_a_identity(tmp_path: Path) -> None:
    ws = Workspace(game_dir=FIXTURE, work_dir=tmp_path)
    result = RenpyAdapter().verify_round_trip(ws)
    assert result.identity.passed, _failures(list(result.identity.failures))
    assert result.identity.units_checked >= 15, (
        f"only {result.identity.units_checked} units extracted from Tier 0; "
        "the fixture covers more — the parser regressed"
    )


def test_gate_b_expansion(tmp_path: Path) -> None:
    ws = Workspace(game_dir=FIXTURE, work_dir=tmp_path)
    result = RenpyAdapter().verify_round_trip(ws)
    assert result.expansion.passed, _failures(list(result.expansion.failures))


def test_probe_detects_renpy() -> None:
    probe = RenpyAdapter().probe(FIXTURE)
    assert probe is not None
    assert probe.engine == "renpy"
    assert probe.confidence >= 0.5, probe
    assert any(".rpy" in e for e in probe.evidence), probe.evidence
