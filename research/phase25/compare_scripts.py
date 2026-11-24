#!/usr/bin/env python3
"""Diff Black Label's stage scripts against the PS2 executable's (research/phase25). Standard library only.

    python3 research/phase25/compare_scripts.py BLRAM.bin SLPM_663.01

BLRAM.bin: BL main RAM 0C000000-0C7FFFFF as the CPU sees it (big-endian), from research/phase25/bl_dump_ram.lua.
SLPM_663.01: the retail PS2 executable. Neither file is in the repository.

Each stage script starts two bytes before its FF0F <stage> command (BL 0C200320 ... 0C2035FC, PS2 0x001EB048 ...
0x001EE4F0) and runs to the next one. The scripts are 16-bit words (BL big-endian, PS2 little-endian): time-ordered
records (time, type, position, subtype, flags), commands 0xFFxx with arguments, and sub-scripts reached through
pointer tables. The word diff below drops the differences that are layout only: PS2 alignment zeros, pointer
tables (BL 0C20xxxx vs PS2 001Exxxx / 0033xxxx), PS2-only FF2A / FF10 / FF27 commands. What remains needs a look:
a block that only moved (difflib pairs repeated sub-scripts arbitrarily) shows up as a delete plus an insert of
the same words.
"""
from __future__ import annotations

import difflib
import struct
import sys


def find_all(buf: bytes, pat: bytes):
    i = buf.find(pat)
    while i >= 0:
        if i % 2 == 0:
            yield i
        i = buf.find(pat, i + 1)


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 2:
        print(__doc__)
        return 2
    bl = open(argv[0], "rb").read()
    elf = open(argv[1], "rb").read()

    def bw(a):
        return struct.unpack_from(">H", bl, a - 0x0C000000)[0]

    def pw(a):
        return struct.unpack_from("<H", elf, a - 0x100000 + 128)[0]

    bl_at, ps_at = {}, {}
    for st in range(1, 7):
        bl_at[st] = 0x0C000000 + next(find_all(bl, struct.pack(">2H", 0xFF0F, st))) - 2
        ps = [0x100000 + i - 128 for i in find_all(elf, struct.pack("<2H", 0xFF0F, st))
              if 0x1E0000 < 0x100000 + i - 128 < 0x1F2000]
        ps_at[st] = ps[0] - 2
    bl_ends = sorted(bl_at.values()) + [bl_at[6] + 0x1400]
    ps_ends = sorted(ps_at.values()) + [ps_at[6] + 0x1400]

    def layout_only(b, p):
        if not b and (all(x == 0 for x in p) or p[:1] in ([0xFF2A], [0xFF27])):
            return True
        def ptrs(ws, hi_first):
            if len(ws) % 2:
                return all(x == 0 for x in ws)
            for k in range(0, len(ws), 2):
                hi, lo = (ws[k], ws[k + 1]) if hi_first else (ws[k + 1], ws[k])
                if not (hi in (0x0C20, 0x001E, 0x001F, 0x0033) or (hi == 0 and lo == 0)):
                    return False
            return True
        p2 = p[p.index(0x7D30) - 1:] if 0x7D30 in p else p
        return (not b or ptrs(b, True)) and (not p or ptrs(p2, False) or 0xFF10 in p)

    for st in range(1, 7):
        b0, p0 = bl_at[st], ps_at[st]
        b1, p1 = min(x for x in bl_ends if x > b0), min(x for x in ps_ends if x > p0)
        B = [bw(a) for a in range(b0, b1, 2)]
        P = [pw(a) for a in range(p0, p1, 2)]
        sm = difflib.SequenceMatcher(None, B, P, autojunk=False)
        print(f"=== stage {st}: BL {b0:08X} ({len(B)} words), PS2 {p0:08X} ({len(P)} words)")
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            b, p = B[i1:i2], P[j1:j2]
            if op == "equal" or layout_only(b, p):
                continue
            ctx = " ".join(f"{x:04X}" for x in B[max(0, i1 - 8):i1])
            print(f"  {op} BL+{2 * i1:X} ({b0 + 2 * i1:08X}) PS2+{2 * j1:X} ({p0 + 2 * j1:08X})  after ..{ctx}")
            print("    BL : " + " ".join(f"{x:04X}" for x in b[:60]))
            print("    PS2: " + " ".join(f"{x:04X}" for x in p[:60]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
