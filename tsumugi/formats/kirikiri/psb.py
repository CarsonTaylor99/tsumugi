"""PSB v2/v3 reader (KiriKiriZ compiled .scn scenarios and other PSB assets).

Read-only. Format reimplemented from FreeMote (Psb.cs / PsbValues.cs) — the
sanctioned dev-time way to build a deterministic parser (hard rule 1).

Numbers are little-endian, width-prefixed. An array is
`<count-width byte><count><entry-width byte><packed entries>`, both widths
encoded as `byte - 0x0C`. Writing PSB (offset/string-table rebuild) is the
Phase 6 job and is deliberately not here.
"""

from __future__ import annotations

import struct
from typing import Union

PsbValue = Union[
    None, bool, int, float, str, "list[PsbValue]", "dict[str, PsbValue]"
]

_MAGIC = b"PSB\x00"


class PsbError(Exception):
    pass


class PsbReader:
    def __init__(self, data: bytes) -> None:
        if data[:4] != _MAGIC:
            raise PsbError(f"not a PSB file (magic {data[:4]!r})")
        self._d = data
        self.version: int = struct.unpack_from("<H", data, 4)[0]
        (
            _off_encrypt,
            self._off_names,
            self._off_strings,
            self._off_strings_data,
            self._off_chunk_offsets,
            self._off_chunk_lengths,
            self._off_chunk_data,
            self._off_entries,
        ) = struct.unpack_from("<8I", data, 8)
        self._names: list[str] = []
        self._string_offsets: list[int] = []
        self._load_names()
        self._string_offsets, _ = self._read_array(self._off_strings)

    @staticmethod
    def _uint(b: bytes) -> int:
        return int.from_bytes(b, "little")

    def _read_array(self, pos: int) -> tuple[list[int], int]:
        d = self._d
        n = d[pos] - 0x0C
        pos += 1
        count = self._uint(d[pos : pos + n])
        pos += n
        entry_len = d[pos] - 0x0C
        pos += 1
        vals = [
            self._uint(d[pos + i * entry_len : pos + (i + 1) * entry_len])
            for i in range(count)
        ]
        return vals, pos + entry_len * count

    def _load_names(self) -> None:
        p = self._off_names
        charset, p = self._read_array(p)
        names_data, p = self._read_array(p)
        name_indexes, _ = self._read_array(p)
        names: list[str] = []
        for start in name_indexes:
            cur = names_data[start]
            acc = bytearray()
            while cur != 0:
                code = names_data[cur]
                acc.append(cur - charset[code])
                cur = code
            acc.reverse()
            names.append(acc.decode("utf-8", "replace"))
        self._names = names

    def _string(self, index: int) -> str:
        start = self._off_strings_data + self._string_offsets[index]
        end = self._d.index(b"\x00", start)
        return self._d[start:end].decode("utf-8", "replace")

    def _unpack(self, pos: int) -> PsbValue:
        d = self._d
        t = d[pos]
        pos += 1
        if t in (0x00, 0x01):
            return None
        if t == 0x02:
            return False
        if t == 0x03:
            return True
        if t == 0x04:
            return 0
        if 0x05 <= t <= 0x0C:  # NumberN1..N8
            n = t - 0x04
            return self._uint(d[pos : pos + n])
        if 0x0D <= t <= 0x14:  # int array
            vals, _ = self._read_array(pos - 1)
            return list(vals)
        if 0x15 <= t <= 0x18:  # StringN1..N4
            n = t - 0x14
            return self._string(self._uint(d[pos : pos + n]))
        if 0x19 <= t <= 0x1C:  # ResourceN1..N4
            n = t - 0x18
            return {"__resource__": self._uint(d[pos : pos + n])}
        if t == 0x1D:
            return 0.0
        if t == 0x1E:
            return struct.unpack_from("<f", d, pos)[0]
        if t == 0x1F:
            return struct.unpack_from("<d", d, pos)[0]
        if t == 0x20:  # List
            offsets, base = self._read_array(pos)
            return [self._unpack(base + off) for off in offsets]
        if t == 0x21:  # Objects (dict)
            names, p = self._read_array(pos)
            offsets, base = self._read_array(p)
            return {
                self._names[nidx]: self._unpack(base + off)
                for nidx, off in zip(names, offsets)
            }
        raise PsbError(f"unknown PSB type 0x{t:02x} at offset {pos - 1}")

    def root(self) -> PsbValue:
        return self._unpack(self._off_entries)
