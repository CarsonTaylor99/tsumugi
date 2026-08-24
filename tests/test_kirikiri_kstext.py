"""KiriKiri text codec: scrambled (mode 0/1) and plain, byte-identical."""

import struct
import zlib

import pytest

from tsumugi.formats.kirikiri.kstext import KsCodec, decode, encode


@pytest.mark.parametrize("mode", [0, 1])
def test_scrambled_roundtrip_is_byte_identical(mode: int) -> None:
    text = "【エリカ】テスト。[r]\r\n改行と記号：〜！？[p]\r\n"
    raw = encode(text, KsCodec(scramble_mode=mode, encoding="utf-16-le"))
    assert raw[:2] == b"\xfe\xfe" and raw[2] == mode and raw[3:5] == b"\xff\xfe"
    decoded = decode(raw)
    assert decoded is not None
    got_text, codec = decoded
    assert got_text == text
    assert codec.scramble_mode == mode
    assert encode(got_text, codec) == raw  # the property Gate A relies on


def test_mode1_is_the_known_bitswap() -> None:
    # 'A' = 0x0041 -> bitswap -> 0x0082; verify against the documented formula.
    raw = encode("A", KsCodec(scramble_mode=1, encoding="utf-16-le"))
    unit = raw[5] | (raw[6] << 8)
    assert unit == (((0x0041 & 0xAAAA) >> 1) | ((0x0041 & 0x5555) << 1))


def test_plain_paths_roundtrip() -> None:
    for enc, blob in [
        ("cp932", "地の文。[p]\r\n".encode("cp932")),
        ("utf-16-le", b"\xff\xfe" + "台詞。[r]\r\n".encode("utf-16-le")),
    ]:
        decoded = decode(blob)
        assert decoded is not None, enc
        text, codec = decoded
        assert codec.scramble_mode is None and codec.encoding == enc
        assert encode(text, codec) == blob


def test_mode2_decodes_but_refuses_reencode() -> None:
    text = "圧縮されたテキスト。\r\n"
    payload = text.encode("utf-16-le")
    comp = zlib.compress(payload)
    raw = (
        b"\xfe\xfe\x02\xff\xfe"
        + struct.pack("<q", len(comp))
        + struct.pack("<q", len(payload))
        + comp
    )
    decoded = decode(raw)
    assert decoded is not None
    got, codec = decoded
    assert got == text and codec.scramble_mode == 2
    with pytest.raises(NotImplementedError):
        encode(got, codec)


def test_odd_length_and_bad_bom_refused() -> None:
    assert decode(b"\xfe\xfe\x01\xff\xfe\x00") is None  # odd payload
    assert decode(b"\xfe\xfe\x01\x00\x00rest") is None  # missing BOM
    assert decode(b"\xfe\xfe\x09\xff\xfeabcd") is None  # unknown mode
