"""XP3 (KiriKiri) container: clean-room reader.

Reads the index of any XP3 and extracts files from *unencrypted* archives.
Commercial titles usually set the protect flag and encrypt contents with a
per-title cipher (cxdec); those are reported, not guessed at — Stage 1
shells out to GARbro / a KrkrExtract dump for them (docs/02).

Writing (patch2.xp3) is Phase 6 work; revisit `construct` then so parse and
build share one definition.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

MAGIC = b"XP3\r\n \n\x1a\x8bg\x01"


class Xp3Error(Exception):
    pass


@dataclass(frozen=True)
class Segment:
    compressed: bool
    offset: int
    original_size: int
    stored_size: int


@dataclass(frozen=True)
class Entry:
    name: str
    protected: bool
    segments: list[Segment]
    adler32: int | None


@dataclass(frozen=True)
class Xp3Index:
    entries: list[Entry]
    index_protected: bool

    @property
    def any_protected(self) -> bool:
        return self.index_protected or any(e.protected for e in self.entries)


def _u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def _u64(b: bytes, o: int) -> int:
    return struct.unpack_from("<Q", b, o)[0]


def read_index(path: Path) -> Xp3Index:
    with path.open("rb") as f:
        head = f.read(19)
        if head[:11] != MAGIC:
            raise Xp3Error(f"{path.name}: not an XP3 archive (magic {head[:11].hex()})")
        cursor = _u64(head, 11)
        # v2 header: cursor points at [minor u32][0x80][index offset u64]
        f.seek(cursor)
        ext = f.read(13)
        index_ofs = _u64(ext, 5) if len(ext) == 13 and ext[4] == 0x80 else cursor
        f.seek(index_ofs)
        flag = f.read(1)[0]
        index_protected = bool(flag & 0x80)
        method = flag & 0x07
        if method == 1:
            csize = _u64(f.read(8), 0)
            usize = _u64(f.read(8), 0)
            try:
                raw = zlib.decompress(f.read(csize))
            except zlib.error as e:
                raise Xp3Error(
                    f"{path.name}: index inflate failed ({e}) — protected index"
                ) from e
            if len(raw) != usize:
                raise Xp3Error(
                    f"{path.name}: index size {len(raw)}, header said {usize}"
                )
        elif method == 0:
            usize = _u64(f.read(8), 0)
            raw = f.read(usize)
        else:
            raise Xp3Error(f"{path.name}: unknown index compress method {method}")
    entries = _parse_entries(raw)
    if not entries and index_protected:
        raise Xp3Error(
            f"{path.name}: index is protected (per-title encryption) — "
            "dump with GARbro or KrkrExtract, then point Tsumugi at the dump"
        )
    return Xp3Index(entries=entries, index_protected=index_protected)


def _parse_entries(raw: bytes) -> list[Entry]:
    entries: list[Entry] = []
    p = 0
    while p + 12 <= len(raw):
        tag, size = raw[p : p + 4], _u64(raw, p + 4)
        body = raw[p + 12 : p + 12 + size]
        if tag == b"File":
            entry = _parse_file_chunk(body)
            if entry is not None:
                entries.append(entry)
        p += 12 + size
    return entries


def _parse_file_chunk(body: bytes) -> Entry | None:
    name: str | None = None
    protected = False
    segments: list[Segment] = []
    adler: int | None = None
    q = 0
    while q + 12 <= len(body):
        tag, size = body[q : q + 4], _u64(body, q + 4)
        sub = body[q + 12 : q + 12 + size]
        if tag == b"info":
            flags = _u32(sub, 0)
            protected = bool(flags & 0x80000000)
            nlen = struct.unpack_from("<H", sub, 20)[0]
            name = sub[22 : 22 + nlen * 2].decode("utf-16-le", errors="replace")
        elif tag == b"segm":
            for s in range(0, len(sub) - 27, 28):
                segments.append(
                    Segment(
                        compressed=bool(_u32(sub, s) & 1),
                        offset=_u64(sub, s + 4),
                        original_size=_u64(sub, s + 12),
                        stored_size=_u64(sub, s + 20),
                    )
                )
        elif tag == b"adlr":
            adler = _u32(sub, 0)
        q += 12 + size
    if name is None:
        return None
    return Entry(name=name, protected=protected, segments=segments, adler32=adler)


def extract_entry(archive: BinaryIO, entry: Entry) -> bytes:
    if entry.protected:
        raise Xp3Error(f"{entry.name}: protected (encrypted) — needs an external dump")
    parts: list[bytes] = []
    for seg in entry.segments:
        archive.seek(seg.offset)
        blob = archive.read(seg.stored_size)
        if seg.compressed:
            blob = zlib.decompress(blob)
        if len(blob) != seg.original_size:
            raise Xp3Error(
                f"{entry.name}: segment expanded to {len(blob)} bytes, "
                f"expected {seg.original_size}"
            )
        parts.append(blob)
    data = b"".join(parts)
    if entry.adler32 is not None and zlib.adler32(data) != entry.adler32:
        raise Xp3Error(f"{entry.name}: adler32 mismatch — corrupt or encrypted")
    return data


def unpack(path: Path, dest: Path) -> int:
    """Extract every unprotected entry. Returns count written."""
    index = read_index(path)
    count = 0
    with path.open("rb") as f:
        for entry in index.entries:
            safe = entry.name.replace("\\", "/")
            if safe.startswith("/") or ".." in safe.split("/"):
                continue  # never write outside dest
            out = dest / safe
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(extract_entry(f, entry))
            count += 1
    return count
