"""Parser and masking unit tests. Failures carry values, not verdicts."""

from pathlib import Path

from tsumugi.core.models import PlaceholderKind, UnitKind, Workspace
from tsumugi.formats.renpy.adapter import RenpyAdapter
from tsumugi.formats.renpy.parser import escape, parse_rpy, unescape
from tsumugi.formats.renpy.tags import mask

FIXTURE = Path(__file__).parent / "fixtures" / "renpy_tier0"


def test_say_forms() -> None:
    says = parse_rpy(
        'label x:\n'
        '    "narration"\n'
        '    e "dialogue"\n'
        '    e happy "with attribute"\n'
        '    "Display Name" "string-name say"\n'
        '    play music "not_dialogue.ogg"\n'
        '    define e = Character("not dialogue")\n'
    )
    kinds = [(s.kind, s.speaker, s.raw_content) for s in says]
    assert kinds == [
        (UnitKind.NARRATION, None, "narration"),
        (UnitKind.DIALOGUE, "e", "dialogue"),
        (UnitKind.DIALOGUE, "e", "with attribute"),
        (UnitKind.DIALOGUE, "Display Name", "string-name say"),
    ], kinds


def test_menu_choices() -> None:
    says = parse_rpy(
        "menu:\n"
        '    "Choice A":\n'
        "        jump a\n"
        '    "Choice B" if flag:\n'
        "        jump b\n"
        '"after menu"\n'
    )
    assert [(s.kind, s.raw_content) for s in says] == [
        (UnitKind.CHOICE, "Choice A"),
        (UnitKind.CHOICE, "Choice B"),
        (UnitKind.NARRATION, "after menu"),
    ]


def test_translate_blocks_skipped() -> None:
    says = parse_rpy(
        "translate english start_1:\n"
        '    e "already translated"\n'
        '"outside"\n'
    )
    assert [s.raw_content for s in says] == ["outside"]


def test_mask_kinds() -> None:
    result = mask("A{i}B{/i}{w=0.5}[name]C{unknown}")
    assert result is not None
    masked, ph = result
    assert masked == "A⟦0⟧B⟦1⟧⟦2⟧⟦3⟧C⟦4⟧", masked
    assert [p.kind for p in ph] == [
        PlaceholderKind.STYLE_OPEN,
        PlaceholderKind.STYLE_CLOSE,
        PlaceholderKind.WAIT,
        PlaceholderKind.VAR,
        PlaceholderKind.OPAQUE,
    ], ph


def test_mask_literal_braces_stay_text() -> None:
    result = mask("a {{literal}} and [[literal]]")
    assert result is not None
    masked, ph = result
    assert masked == "a {{literal}} and [[literal]]"
    assert ph == []


def test_mask_refuses_unbalanced() -> None:
    assert mask("broken {i tag") is None
    assert mask("has a ⟦0⟧ glyph") is None


def test_escape_roundtrip() -> None:
    for raw in ['plain', 'a \\"quote\\"', 'line\\nbreak', 'tab\\there', 'back\\\\slash']:
        unescaped = unescape(raw)
        assert unescaped is not None, raw
        assert escape(unescaped) == raw, (raw, escape(unescaped))
    assert unescape("bad \\' escape") is None
    assert unescape("trailing\\") is None


def test_non_canonical_literal_is_skipped_not_guessed(tmp_path: Path) -> None:
    game = tmp_path / "game"
    game.mkdir()
    (game / "s.rpy").write_text(
        'label x:\n    "ok line"\n    "bad \\\' line"\n', encoding="utf-8"
    )
    units = list(
        RenpyAdapter().extract(Workspace(game_dir=tmp_path, work_dir=tmp_path / "w"))
    )
    assert [u.source_text for u in units] == ["ok line"]
