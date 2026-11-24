#!/usr/bin/env python3
"""Black Label's ship-select theme on the patched disc (research/phase23). Python standard library only.

From the user's own ibarablk sound ROMs (u23 + u24, checked by CRC): decode phrase 0 (amm_decode), encode it as a
PS2 BGM stream (bg00_stream), and add it to the game's resource archive without growing the image:

* the stream goes into the zero gap just below IBARAR.PDM (the gap after DAMMY1G.DAT), at LBA X;
* IBARAR.PDM's directory record starts at X instead (its size grows by the same amount), so every retail entry
  keeps its disc sectors; IBARAR.TBL gets that amount added to every offset and one new entry (offset 0) at the
  end — 16 more bytes inside the table's last sector;
* the KURO executable's music slot ("BLSELECT-MUS-01") gets the new entry's index.
"""
from __future__ import annotations

import struct
import zipfile
import zlib
from pathlib import Path

SECTOR = 2048
U23_SIZE, U23_CRC = 0x400000, 0xA436BB22
U24_SIZE, U24_CRC = 0x400000, 0xD11AB6B6
MUSIC_TAG = b"BLSELECT-MUS-01\0"
SELECT_PHRASE = 0
GAIN = 0.5  # the decoded theme is ~2x the retail tracks' level (RMS 14,500 vs 7,048)


def read_sound_roms(path):
    """(u23, u24) from an ibarablk zip, or from u23 / u24 files next to the given file; None if absent."""
    path = Path(path)
    want = {U23_CRC: None, U24_CRC: None}
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            for i in z.infolist():
                if i.file_size == 0x400000 and i.CRC in want:
                    want[i.CRC] = z.read(i)
    else:
        for name in ("u23", "u24"):
            f = path.parent / name
            if f.is_file() and f.stat().st_size == 0x400000:
                d = f.read_bytes()
                c = zlib.crc32(d)
                if c in want:
                    want[c] = d
    if want[U23_CRC] is None or want[U24_CRC] is None:
        return None
    return want[U23_CRC], want[U24_CRC]


def select_theme_stream(u23: bytes, u24: bytes) -> bytes:
    import amm_decode
    import bg00_stream
    rom = amm_decode.sound_rom(u23, u24)
    pcm, rate, nch = amm_decode.decode_phrase(rom, SELECT_PHRASE)
    if nch != 1 or not pcm:
        raise SystemExit("unexpected Black Label select theme format")
    return bg00_stream.stream_from_pcm(pcm, rate, GAIN)


def _root_records(f):
    """{name: (byte position of the record, lba, size)} for the root directory."""
    f.seek(16 * SECTOR)
    pvd = f.read(SECTOR)
    lba, size = struct.unpack_from("<I", pvd, 158)[0], struct.unpack_from("<I", pvd, 166)[0]
    f.seek(lba * SECTOR)
    d = f.read(size)
    out, i = {}, 0
    while i < len(d):
        n = d[i]
        if n == 0:
            i = (i // SECTOR + 1) * SECTOR
            continue
        name = d[i + 33:i + 33 + d[i + 32]].split(b";")[0].decode("latin-1")
        out[name] = (lba * SECTOR + i, struct.unpack_from("<I", d, i + 2)[0], struct.unpack_from("<I", d, i + 10)[0])
        i += n
    return out


def _all_extents(f):
    """(lba, size) of every file and directory on the disc, subdirectories included (IOP/ holds modules)."""
    f.seek(16 * SECTOR)
    pvd = f.read(SECTOR)
    todo = [(struct.unpack_from("<I", pvd, 158)[0], struct.unpack_from("<I", pvd, 166)[0])]
    seen, out = set(), []
    while todo:
        lba, size = todo.pop()
        if lba in seen:
            continue
        seen.add(lba)
        out.append((lba, size))
        f.seek(lba * SECTOR)
        d = f.read(size)
        i = 0
        while i < len(d):
            n = d[i]
            if n == 0:
                i = (i // SECTOR + 1) * SECTOR
                continue
            name_len = d[i + 32]
            rl, rs = struct.unpack_from("<I", d, i + 2)[0], struct.unpack_from("<I", d, i + 10)[0]
            if not (name_len == 1 and d[i + 33] in (0, 1)):
                if d[i + 25] & 2:
                    todo.append((rl, rs))
                else:
                    out.append((rl, rs))
            i += n
    return out


def _set_extent(f, rec_pos: int, lba: int, size: int):
    f.seek(rec_pos + 2)
    f.write(struct.pack("<I", lba) + struct.pack(">I", lba) + struct.pack("<I", size) + struct.pack(">I", size))


def rebuild_tbl(tbl: bytes, shift: int, new_length: int) -> bytes:
    """IBARAR.TBL with every offset + shift and one more entry (offset 0, new_length) at the end."""
    if tbl[:4] != b"TBL\x04":
        raise SystemExit("IBARAR.TBL: unexpected signature")
    u = lambda o: struct.unpack_from("<I", tbl, o)[0]
    n, rs = u(8) >> 16, u(8) & 0xFFFF
    if rs != 20 + 4 * n:
        raise SystemExit("IBARAR.TBL: unexpected layout")
    lengths, offsets = [], []
    for i in range(n):
        rp = u(20 + 4 * i)
        offp, ln = u(rp), u(rp + 4)
        lengths.append(ln)
        offsets.append(u(offp) + shift)
    lengths.append(new_length)
    offsets.append(0)
    m = n + 1
    rs2 = 20 + 4 * m
    off_tab = rs2 + 8 * m
    out = bytearray(tbl[:20])
    struct.pack_into("<I", out, 8, (m << 16) | rs2)
    out += b"".join(struct.pack("<I", rs2 + 8 * i) for i in range(m))
    out += b"".join(struct.pack("<II", off_tab + 4 * i, lengths[i]) for i in range(m))
    out += b"".join(struct.pack("<I", o) for o in offsets)
    return bytes(out)


def inject_bl_music(iso, tag_at: int, stream: bytes) -> int:
    """Add the stream to the archive of the disc image `iso` (in place) and point the music slot at it. Returns
    the new archive entry index."""
    if len(stream) % SECTOR:
        stream += bytes(SECTOR - len(stream) % SECTOR)
    with open(iso, "r+b") as f:
        recs = _root_records(f)
        pdm_pos, pdm_lba, pdm_size = recs["IBARAR.PDM"]
        tbl_pos, tbl_lba, tbl_size = recs["IBARAR.TBL"]
        # the top of the largest empty stretch between file extents below the archive (the retail zero gap; the
        # builder may already keep the moved executable at its bottom)
        ext = sorted((lba, lba + (size + SECTOR - 1) // SECTOR) for lba, size in _all_extents(f) if lba < pdm_lba)
        gaps, end = [], 0
        for lba, e in ext:
            if lba > end:
                gaps.append((lba - end, lba))
            end = max(end, e)
        top = max(gaps)[1]
        sectors = len(stream) // SECTOR
        x = top - sectors
        f.seek(x * SECTOR)
        if any(f.read(len(stream))):
            raise SystemExit("the free area below the resource archive is not empty; not adding the music")
        shift = (pdm_lba - x) * SECTOR
        f.seek(tbl_lba * SECTOR)
        tbl = f.read(tbl_size)
        n = struct.unpack_from("<I", tbl, 8)[0] >> 16
        new_tbl = rebuild_tbl(tbl, shift, len(stream))
        if (len(new_tbl) + SECTOR - 1) // SECTOR > (tbl_size + SECTOR - 1) // SECTOR:
            raise SystemExit("IBARAR.TBL has no room for one more entry")
        f.seek(x * SECTOR)
        f.write(stream)
        f.seek(tbl_lba * SECTOR)
        f.write(new_tbl)
        _set_extent(f, pdm_pos, x, pdm_size + shift)
        _set_extent(f, tbl_pos, tbl_lba, len(new_tbl))
        f.seek(tag_at + 16)
        f.write(struct.pack("<I", n))
    return n
