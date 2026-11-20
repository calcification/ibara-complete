#!/usr/bin/env python3
"""Offline helpers for PCSX2 savestates (.p2s) and EE RAM dumps, to locate Ibara PS2 game fields.

A savestate holds the user's own RAM contents: keep .p2s/.bin files local, never commit them.

    # extract the 32 MiB EE RAM
    python3 scripts/p2s_tools.py extract state.p2s -o eeMemory.bin
    # find a field that tracks a value you controlled (e.g. ship moved left -> right)
    python3 scripts/p2s_tools.py find left.p2s=0 mid.p2s=1 right.p2s=2 --range 0044C380:0044C610 --relation monotonic
    # words that differ between two groups (button released vs held)
    python3 scripts/p2s_tools.py find up1.p2s=0 up2.p2s=0 dn1.p2s=1 dn2.p2s=1 --relation group
    # check the hook code cave is zero
    python3 scripts/p2s_tools.py cave title.p2s arcade.p2s arrange.p2s

PCSX2 2.x savestates are zip archives whose members may be zstd-compressed (method 93); that needs
`pip install zstandard` on Python < 3.14. Stored and deflate members need nothing extra.
"""
from __future__ import annotations

import argparse
import struct
import sys
import zipfile
import zlib
from pathlib import Path

EE_SIZE = 32 * 1024 * 1024
CAVE = (0x000C0000, 0x00100000)


def _zstd_decompress(blob: bytes) -> bytes:
    try:
        from compression import zstd  # Python 3.14+
        return zstd.decompress(blob)
    except ImportError:
        pass
    try:
        import zstandard
    except ImportError as e:  # pragma: no cover - environment dependent
        raise SystemExit("zstd-compressed savestate: pip install zstandard") from e
    return zstandard.ZstdDecompressor().decompressobj().decompress(blob)


def _read_member(path: Path, info: zipfile.ZipInfo) -> bytes:
    with path.open("rb") as fh:
        fh.seek(info.header_offset)
        hdr = fh.read(30)
        if hdr[:4] != b"PK\x03\x04":
            raise ValueError("bad local header")
        nlen, xlen = struct.unpack_from("<HH", hdr, 26)
        fh.seek(info.header_offset + 30 + nlen + xlen)
        blob = fh.read(info.compress_size)
    if info.compress_type == zipfile.ZIP_STORED:
        return blob
    if info.compress_type == zipfile.ZIP_DEFLATED:
        return zlib.decompress(blob, -15)
    if info.compress_type == 93:
        return _zstd_decompress(blob)
    raise ValueError(f"unsupported zip method {info.compress_type}")


def load_ee(path: Path) -> bytes:
    """EE RAM from a .p2s savestate or a raw 32 MiB dump."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            members = [i for i in zf.infolist() if i.filename.lower().endswith("eememory.bin")]
        if not members:
            raise ValueError(f"{path}: no eeMemory.bin member")
        data = _read_member(path, members[0])
    else:
        data = path.read_bytes()
    if len(data) != EE_SIZE:
        raise ValueError(f"{path}: EE RAM is {len(data)} bytes, expected {EE_SIZE}")
    return data


FMT = {"u8": ("<B", 1), "s8": ("<b", 1), "u16": ("<H", 2), "s16": ("<h", 2), "u32": ("<I", 4), "s32": ("<i", 4),
       "fx16": ("<i", 4)}


def value(ram: bytes, addr: int, t: str) -> int:
    f, _n = FMT[t]
    v = struct.unpack_from(f, ram, addr)[0]
    return v >> 16 if t == "fx16" else v


def find(states: list[tuple[bytes, float]], lo: int, hi: int, types: list[str], relation: str, limit: int):
    out = []
    labels = [lab for _r, lab in states]
    order = sorted(range(len(states)), key=lambda i: labels[i])
    for t in types:
        size = FMT[t][1]
        for a in range(lo, hi - size + 1, size):
            vals = [value(r, a, t) for r, _ in states]
            if len(set(vals)) < 2:
                continue
            if relation == "equal":
                ok = all(v == lab for v, lab in zip(vals, labels))
                score = 1.0
            elif relation == "monotonic":
                seq = [vals[i] for i in order]
                lab = [labels[i] for i in order]
                inc = all(seq[i] < seq[i + 1] for i in range(len(seq) - 1) if lab[i] < lab[i + 1])
                dec = all(seq[i] > seq[i + 1] for i in range(len(seq) - 1) if lab[i] < lab[i + 1])
                same = all(seq[i] == seq[i + 1] for i in range(len(seq) - 1) if lab[i] == lab[i + 1])
                ok = (inc or dec) and same
                score = 1.0 if ok else 0.0
            elif relation == "group":
                groups: dict[float, set[int]] = {}
                for v, lab in zip(vals, labels):
                    groups.setdefault(lab, set()).add(v)
                sets = list(groups.values())
                ok = all(len(s) == 1 for s in sets) and len({next(iter(s)) for s in sets}) == len(sets)
                score = 1.0
            else:
                raise ValueError(relation)
            if ok:
                out.append((score, a, t, vals))
    out.sort(key=lambda x: (-x[0], x[1]))
    return out[:limit]


def cave_report(ram: bytes) -> list[int]:
    lo, hi = CAVE
    return [a for a in range(lo, hi, 4) if struct.unpack_from("<I", ram, a)[0]]


def parse_state(arg: str) -> tuple[Path, float]:
    if "=" not in arg:
        raise SystemExit(f"state needs a label: {arg}=<number>")
    p, lab = arg.rsplit("=", 1)
    return Path(p), float(lab)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("state", type=Path)
    e.add_argument("-o", "--out", type=Path, required=True)
    f = sub.add_parser("find")
    f.add_argument("states", nargs="+", help="file=label")
    f.add_argument("--range", default="00100000:02000000", help="HEXLO:HEXHI")
    f.add_argument("--types", default="u8,s16,s32,fx16")
    f.add_argument("--relation", choices=["monotonic", "equal", "group"], default="monotonic")
    f.add_argument("--limit", type=int, default=60)
    c = sub.add_parser("cave")
    c.add_argument("states", nargs="+", type=Path)
    args = ap.parse_args(argv)

    if args.cmd == "extract":
        args.out.write_bytes(load_ee(args.state))
        print(f"wrote {args.out} ({EE_SIZE} bytes)")
    elif args.cmd == "find":
        lo, hi = (int(x, 16) for x in args.range.split(":"))
        states = [(load_ee(p), lab) for p, lab in map(parse_state, args.states)]
        hits = find(states, lo, hi, args.types.split(","), args.relation, args.limit)
        for _s, a, t, vals in hits:
            print(f"{a:08X} {t:4} " + " ".join(str(v) for v in vals))
        print(f"{len(hits)} candidate(s)")
    elif args.cmd == "cave":
        bad = 0
        for p in args.states:
            nz = cave_report(load_ee(p))
            bad += bool(nz)
            print(f"{p}: {'FREE' if not nz else f'{len(nz)} non-zero words, first {nz[0]:08X}'}")
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
