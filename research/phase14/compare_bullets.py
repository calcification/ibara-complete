#!/usr/bin/env python3
"""Phase 14: compare BL (MAME, bullet_log.lua) and PS2 (spawnlog.c bullet log) enemy-bullet timelines.

Both logs are aligned at the first type-54 enemy spawn of their spawn logs and binned (default 500 frames):
bullet count, BL mean speed (px/frame, measured 6 frames after spawn), and the most common bullet types (+04).

    python3 research/phase14/compare_bullets.py bl_spawns.txt bl_bullets.txt ps2_spawns.txt ps2_bullets.txt
"""
import collections
import sys


def main(bl_sp, bl_b, ps_sp, ps_b, B=500):
    a_bl = next(int(r[0]) for r in (l.split() for l in open(bl_sp)) if r[3] == "54")
    a_ps = next(int(r[0]) for r in (l.split() for l in open(ps_sp)) if r[2] == "54")
    blb = [(int(r[0]) - a_bl, int(r[2]), float(r[5]), float(r[6])) for r in (l.split() for l in open(bl_b))]
    psb = [(int(r[0]) - a_ps, int(r[2])) for r in (l.split() for l in open(ps_b))]
    span = max(f for f, *_ in blb)
    print("bin          BL n  spd  types                                | PS2 n  types")
    for b in range(0, span + B, B):
        bb = [x for x in blb if b <= x[0] < b + B]
        pp = [x for x in psb if b <= x[0] < b + B]
        tb = collections.Counter(t for _, t, *_ in bb).most_common(3)
        tp = collections.Counter(t for _, t in pp).most_common(3)
        sp = sum((dx * dx + dy * dy) ** .5 for _, _, dx, dy in bb) / len(bb) if bb else 0
        print(f"{b:5d}-{b + B:<6d} {len(bb):4d} {sp:4.2f} {str(tb):36} | {len(pp):4d} {tp}")
    print("totals: BL", len(blb), "PS2", len([x for x in psb if x[0] <= span]))


if __name__ == "__main__":
    main(*sys.argv[1:5])
