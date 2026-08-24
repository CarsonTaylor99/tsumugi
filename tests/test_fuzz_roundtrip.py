"""Mutation fuzzing (docs/10): structurally valid, length-changing mutations,
assert the round-trip holds. Catches fixup bugs a fixed expansion factor
happens to miss."""

from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from tsumugi.core.models import Workspace
from tsumugi.core.sentinels import sentinel
from tsumugi.formats.renpy.adapter import RenpyAdapter

FIXTURE = Path(__file__).parent / "fixtures" / "renpy_tier0"

# No braces/brackets/sentinel glyphs: those are markup, and the placeholder
# contract forbids the model inventing them. Everything else is fair game,
# including quotes, backslashes, newlines, '#', and CJK.
_ALPHABET = (
    "abcdefghij ABCDEFGHIJ 0123456789"
    "\"\\\n\t#'!?.,:;—…~"
    "あいうえおアイウエオ漢字先輩運命"
)


@settings(max_examples=30, deadline=None)
@given(st.lists(st.text(alphabet=_ALPHABET, max_size=60), min_size=1, max_size=30))
def test_arbitrary_targets_roundtrip(texts: list[str]) -> None:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="tsumugi-fuzz-") as td:
        work = Path(td)
        adapter = RenpyAdapter()
        ws = Workspace(game_dir=FIXTURE, work_dir=work)
        units = list(adapter.extract(ws))
        assert units, "fixture yielded no units"

        # Assign generated targets round-robin, appending each unit's own
        # sentinels so the placeholder contract holds by construction.
        for i, u in enumerate(units):
            body = texts[i % len(texts)]
            u.target_text = body + "".join(sentinel(p.index) for p in u.placeholders)

        adapter.inject(ws, units)
        reread_ws = Workspace(game_dir=ws.patched_dir(), work_dir=work / "reread")
        reread = list(adapter.extract(reread_ws))

        assert len(reread) == len(units), (
            f"unit count changed: {len(units)} -> {len(reread)}"
        )
        for before, after in zip(units, reread):
            assert after.source_text == before.target_text, (
                f"unit {before.ordinal} in {before.file}: "
                f"wrote {before.target_text!r}, read back {after.source_text!r}"
            )
