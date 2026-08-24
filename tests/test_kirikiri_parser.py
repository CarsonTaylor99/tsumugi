"""KAG parser and tag-masking unit tests."""

from tsumugi.core.models import PlaceholderKind, UnitKind
from tsumugi.formats.kirikiri.parser import detect_encoding, parse_ks
from tsumugi.formats.kirikiri.tags import mask


def test_line_classification() -> None:
    lines = parse_ks(
        "; comment\n"
        "*label|title\n"
        "@bg storage=\"a.png\"\n"
        "【エリカ】こんにちは。[r]\n"
        "地の文です。[p]\n"
        "[cm]\n"
    )
    got = [(l.kind, l.speaker, l.text) for l in lines]
    assert got == [
        (UnitKind.DIALOGUE, "エリカ", "こんにちは。[r]"),
        (UnitKind.NARRATION, None, "地の文です。[p]"),
        (UnitKind.NARRATION, None, "[cm]"),  # tags-only; adapter drops it later
    ], got


def test_iscript_skipped() -> None:
    lines = parse_ks("[iscript]\nvar x = 1;\n[endscript]\n本文。\n")
    assert [l.text for l in lines] == ["本文。"]


def test_display_name_split() -> None:
    (line,) = parse_ks("【真琴/まこと】ふん。\n")
    assert line.speaker == "真琴"
    assert line.text == "ふん。"


def test_mask_kinds_and_quoted_attrs() -> None:
    result = mask('あの[ruby text="さ]だ"]運命[r]が[emb exp="f.name"]。[p]')
    assert result is not None
    masked, ph = result
    assert masked == "あの⟦0⟧運命⟦1⟧が⟦2⟧。⟦3⟧", masked
    assert [p.kind for p in ph] == [
        PlaceholderKind.RUBY_OPEN,
        PlaceholderKind.LINEBREAK,
        PlaceholderKind.VAR,
        PlaceholderKind.PAGEBREAK,
    ]
    assert ph[0].raw == '[ruby text="さ]だ"]', "quoted ] must stay inside the tag"


def test_mask_literal_brackets() -> None:
    result = mask("括弧は[[こう]]書く。")
    assert result is not None
    masked, ph = result
    assert masked == "括弧は[[こう]]書く。" and ph == []


def test_mask_scn_percent_and_backslash_codes() -> None:
    # Shapes taken verbatim from a real .scn corpus scan (docs/11).
    text = "興奮しているわけではない%p-1;%fＭＳ ゴシック;――%p;%fuser;続き\\n次行\\k待つ"
    result = mask(text, scn_codes=True)
    assert result is not None
    masked, ph = result
    assert masked == "興奮しているわけではない⟦0⟧⟦1⟧――⟦2⟧⟦3⟧続き⟦4⟧次行⟦5⟧待つ", masked
    assert [p.raw for p in ph] == [
        "%p-1;", "%fＭＳ ゴシック;", "%p;", "%fuser;", "\\n", "\\k",
    ], [p.raw for p in ph]
    assert [p.kind for p in ph[:4]] == [PlaceholderKind.OPAQUE] * 4
    assert ph[4].kind == PlaceholderKind.LINEBREAK
    assert ph[5].kind == PlaceholderKind.WAIT


def test_mask_scn_prose_percent_stays_text() -> None:
    result = mask("勝率は１００%です。%50;半分。", scn_codes=True)
    assert result is not None
    masked, ph = result
    assert masked == "勝率は１００%です。⟦0⟧半分。", masked
    assert [p.raw for p in ph] == ["%50;"]


def test_mask_default_leaves_scn_codes_alone() -> None:
    # .ks path unchanged: % and backslash are plain text there.
    result = mask("100%の力\\nで")
    assert result is not None
    assert result[0] == "100%の力\\nで" and result[1] == []


def test_mask_refuses_unterminated() -> None:
    assert mask("broken [r") is None


def test_encoding_detection_roundtrip() -> None:
    cp932 = "【エリカ】こんにちは。[r]\r\n".encode("cp932")
    assert detect_encoding(cp932) == "cp932"
    utf16 = b"\xff\xfe" + "*start\r\n本文。\r\n".encode("utf-16-le")
    assert detect_encoding(utf16) == "utf-16-le"
    assert detect_encoding(b"\xff\x00\xfe\xda\x81") is None
