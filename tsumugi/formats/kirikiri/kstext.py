"""KiriKiri text-file codec: the 0xFE 0xFE scrambled/compressed container that
wraps .ks/.tjs/.csv/.txt content, plus the plain (cp932 / UTF-16 / UTF-8) case.

Algorithm reimplemented from KirikiriTools' Descrambler.cs (arcusmaximus,
MIT) — the sanctioned dev-time way to build a deterministic parser (hard
rule 1). Modes:
  0  conditional XOR   (self-inverse)
  1  16-bit bit-swap   (self-inverse)  ← what the Tier 3 target uses
  2  zlib/deflate      (compression; not byte-reproducible on write)

decode() -> (text, KsCodec) captures exactly what is needed to re-encode a
file byte-identically, which is what Gate A depends on. A file that does not
round-trip (odd-length payload, mode 2, non-canonical encoding) is refused by
returning None so the adapter can skip it loudly rather than corrupt it.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

from tsumugi.formats.kirikiri.parser import detect_encoding

_MAGIC = b"\xfe\xfe"
_BOM = b"\xff\xfe"


@dataclass(frozen=True)
class KsCodec:
    """How a file's text was stored, enough to reproduce its bytes."""

    scramble_mode: int | None  # 0/1 scrambled, 2 compressed, None = plain
    encoding: str  # plain encoding when scramble_mode is None


def _mode0(data: bytearray) -> None:
    for i in range(0, len(data) - 1, 2):
        if data[i + 1] == 0 and data[i] < 0x20:
            continue
        data[i + 1] ^= data[i] & 0xFE
        data[i] ^= 1


def _mode1(data: bytearray) -> None:
    for i in range(0, len(data) - 1, 2):
        c = data[i] | (data[i + 1] << 8)
        c = ((c & 0xAAAA) >> 1) | ((c & 0x5555) << 1)
        data[i] = c & 0xFF
        data[i + 1] = (c >> 8) & 0xFF


def decode(raw: bytes) -> tuple[str, KsCodec] | None:
    if raw[:2] == _MAGIC:
        if len(raw) < 5 or raw[3:5] != _BOM:
            return None
        mode = raw[2]
        body = raw[5:]
        if mode in (0, 1):
            if len(body) % 2 != 0:
                return None
            buf = bytearray(body)
            (_mode0 if mode == 0 else _mode1)(buf)
            text = bytes(buf).decode("utf-16-le")
            codec = KsCodec(scramble_mode=mode, encoding="utf-16-le")
            if encode(text, codec) != raw:  # byte-identity guard
                return None
            return text, codec
        if mode == 2:
            # readable, but zlib output is not byte-reproducible → inject
            # cannot reach Gate A identity for these; decode-only for now.
            if len(body) < 18:
                return None
            usize = struct.unpack_from("<q", body, 8)[0]
            try:
                text = zlib.decompress(body[16:]).decode("utf-16-le")
            except (zlib.error, UnicodeDecodeError):
                return None
            if len(text.encode("utf-16-le")) != usize:
                return None
            return text, KsCodec(scramble_mode=2, encoding="utf-16-le")
        return None

    enc = detect_encoding(raw)
    if enc is None:
        return None
    return raw.decode(enc), KsCodec(scramble_mode=None, encoding=enc)


def encode(text: str, codec: KsCodec) -> bytes:
    if codec.scramble_mode in (0, 1):
        buf = bytearray(text.encode("utf-16-le"))
        (_mode0 if codec.scramble_mode == 0 else _mode1)(buf)
        return _MAGIC + bytes([codec.scramble_mode]) + _BOM + bytes(buf)
    if codec.scramble_mode == 2:
        raise NotImplementedError(
            "mode-2 (compressed) KiriKiri text cannot be re-encoded "
            "byte-identically; no such file seen in the target yet"
        )
    return text.encode(codec.encoding)
