"""Hard rule 2 for the KiriKiri adapter over Tier 0 (cp932 + UTF-16LE)."""

from pathlib import Path

from tsumugi.core.models import UnitKind, Workspace
from tsumugi.formats.kirikiri.adapter import KirikiriAdapter

FIXTURE = Path(__file__).parent / "fixtures" / "kirikiri_tier0"


def test_gate_a_identity(tmp_path: Path) -> None:
    result = KirikiriAdapter().verify_round_trip(
        Workspace(game_dir=FIXTURE, work_dir=tmp_path)
    )
    assert result.identity.passed, [f.message for f in result.identity.failures]
    # cp932, UTF-16LE, and a mode-1 scrambled file must all round-trip.
    assert result.identity.files_checked == 3, "all three storage forms exercised"
    assert result.identity.units_checked >= 8, result.identity.units_checked


def test_gate_b_expansion(tmp_path: Path) -> None:
    result = KirikiriAdapter().verify_round_trip(
        Workspace(game_dir=FIXTURE, work_dir=tmp_path)
    )
    assert result.expansion.passed, [f.message for f in result.expansion.failures]


def test_extraction_shape(tmp_path: Path) -> None:
    units = list(
        KirikiriAdapter().extract(Workspace(game_dir=FIXTURE, work_dir=tmp_path))
    )
    speakers = {u.speaker for u in units if u.speaker}
    assert speakers == {"エリカ", "真琴"}, speakers
    dialogue = [u for u in units if u.kind == UnitKind.DIALOGUE]
    narration = [u for u in units if u.kind == UnitKind.NARRATION]
    assert dialogue and narration
    # 【真琴/まこと】 display-name form: speaker is the id half.
    makoto = [u for u in units if u.speaker == "真琴"]
    assert len(makoto) == 1 and "ふん、" in makoto[0].source_text, makoto
    # iscript contents must never be extracted.
    assert not any("var x" in u.source_text for u in units)
    # Tags are masked, never visible to the model.
    assert not any("[r]" in u.source_text for u in units)
    assert not any("[ruby" in u.source_text for u in units)
