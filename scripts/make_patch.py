#!/usr/bin/env python3
"""Make patcher/ibara_kuro.patch: the difference between the retail disc and a disc built by
scripts/build_black_label_iso.py, in a form that carries no game data.

    python3 scripts/make_patch.py 'Ibara (Japan).iso' built.iso --output patcher/ibara_kuro.patch

Every changed byte range of the built disc is encoded as COPY operations from the retail disc (same place, or
anywhere inside the retail executable SLPM_663.01, which is where the baked KURO.ELF comes from) and DATA
operations for bytes that exist nowhere in the retail executable (this project's hook code, patched words,
directory records, the menu label). The script refuses to write a patch whose DATA contains a run longer than
MAX_DATA_RUN bytes, or more than MAX_DATA_TOTAL in all, so a mistake cannot ship the game's own bytes.
Applied by patcher/apply_kuro_patch.py (Python standard library only).
"""
from __future__ import annotations

import argparse
import hashlib
import struct
import sys
import zlib
from pathlib import Path

MAGIC = b"IBKPATCH1\0"
SECTOR = 2048
SOURCE_SIZE = 3_932_848_128
SOURCE_MD5 = "6ba671b5d23155b8254b6f4cefc90ae2"
MAX_DATA_RUN = 8192  # our own hook image is one run (~6.5 KB with the RANK bar code); retail code is copied, never literal
MAX_DATA_TOTAL = 64 * 1024
KEY = 16          # bytes per index key
MIN_COPY = 24     # shortest match taken as a COPY
OP_COPY, OP_DATA = 0, 1


def file_md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def find_file(iso, name: bytes) -> tuple[int, int]:
    """(byte offset, size) of a root-directory file in an ISO 9660 image."""
    iso.seek(16 * SECTOR)
    pvd = iso.read(SECTOR)
    lba, size = struct.unpack_from("<I", pvd, 158)[0], struct.unpack_from("<I", pvd, 166)[0]
    iso.seek(lba * SECTOR)
    d = iso.read(size)
    i = 0
    while i < len(d):
        n = d[i]
        if n == 0:
            i = (i // SECTOR + 1) * SECTOR
            continue
        if d[i + 33:i + 33 + d[i + 32]] == name:
            return struct.unpack_from("<I", d, i + 2)[0] * SECTOR, struct.unpack_from("<I", d, i + 10)[0]
        i += n
    raise ValueError(f"{name!r} not in the root directory")


def changed_ranges(src, dst, size: int) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    pos, step = 0, 1 << 22
    while pos < size:
        a, b = src.read(step), dst.read(step)
        if a != b:
            for k in range(0, len(b), SECTOR):
                if a[k:k + SECTOR] != b[k:k + SECTOR]:
                    s = pos + k
                    if out and out[-1][1] == s:
                        out[-1] = (out[-1][0], s + SECTOR)
                    else:
                        out.append((s, s + SECTOR))
        pos += step
    return out


def encode(target: bytes, at: int, src_same: bytes, exe: bytes, exe_off: int, index: dict) -> list:
    """Ops for target (written at ISO offset `at`); src_same is the retail bytes at the same place."""
    ops: list = []
    lit = bytearray()
    i, n = 0, len(target)

    def flush():
        if lit:
            ops.append((OP_DATA, bytes(lit)))
            lit.clear()

    while i < n:
        best_len, best_src = 0, 0
        # same place in the retail disc
        j = i
        while j < n and target[j] == src_same[j]:
            j += 1
        if j - i >= MIN_COPY:
            best_len, best_src = j - i, at + i
        # anywhere in the retail executable
        key = target[i:i + KEY]
        if len(key) == KEY:
            for cand in index.get(key, ())[:8]:
                k = 0
                while i + k < n and cand + k < len(exe) and target[i + k] == exe[cand + k]:
                    k += 1
                if k > best_len:
                    best_len, best_src = k, exe_off + cand
        if best_len >= MIN_COPY:
            flush()
            ops.append((OP_COPY, best_src, best_len))
            i += best_len
        else:
            lit.append(target[i])
            i += 1
    flush()
    return ops


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=Path)
    ap.add_argument("built", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--note", default="", help="short description stored in the patch (build options)")
    args = ap.parse_args(argv)

    if args.source.stat().st_size != SOURCE_SIZE or file_md5(args.source) != SOURCE_MD5:
        ap.error("source is not the retail 'Ibara (Japan).iso' (SLPM-66301)")
    size = args.built.stat().st_size
    with args.source.open("rb") as src, args.built.open("rb") as dst:
        exe_off, exe_size = find_file(src, b"SLPM_663.01;1")
        src.seek(exe_off)
        exe = src.read(exe_size)
        index: dict = {}
        for p in range(0, len(exe) - KEY, 4):
            index.setdefault(exe[p:p + KEY], []).append(p)
        src.seek(0)
        dst.seek(0)
        ranges = changed_ranges(src, dst, size)
        records = []
        for a, b in ranges:
            dst.seek(a)
            target = dst.read(b - a)
            src.seek(a)
            same = src.read(b - a).ljust(b - a, b"\0")
            records.append((a, b - a, encode(target, a, same, exe, exe_off, index)))
    data_runs = [len(op[1]) for _a, _n, ops in records for op in ops if op[0] == OP_DATA]
    total = sum(data_runs)
    if data_runs and max(data_runs) > MAX_DATA_RUN or total > MAX_DATA_TOTAL:
        raise SystemExit(f"refusing: {total} literal bytes (longest run {max(data_runs)}); game data would be shipped")
    h = hashlib.sha256()
    with args.built.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    body = bytearray()
    body += struct.pack("<QQ", SOURCE_SIZE, size) + bytes.fromhex(SOURCE_MD5) + h.digest()
    note = args.note.encode()[:255]
    body += struct.pack("<B", len(note)) + note
    body += struct.pack("<I", len(records))
    for a, n, ops in records:
        body += struct.pack("<QII", a, n, len(ops))
        for op in ops:
            if op[0] == OP_COPY:
                body += struct.pack("<BQI", OP_COPY, op[1], op[2])
            else:
                body += struct.pack("<BI", OP_DATA, len(op[1])) + op[1]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(MAGIC + zlib.compress(bytes(body), 9))
    print(f"{len(ranges)} changed ranges, {sum(n for _a, n, _o in records):,} bytes changed, "
          f"{total:,} literal bytes (longest run {max(data_runs) if data_runs else 0}); "
          f"patch {args.output.stat().st_size:,} bytes; target SHA-256 {h.hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
