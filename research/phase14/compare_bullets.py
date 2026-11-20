#!/usr/bin/env python3
"""Phase 14: compare BL (MAME) and PS2 (spawnlog.c bullet log) enemy-bullet timelines.

Both logs are aligned at the first spawn of the anchor enemy type (default 54, stage 1) and binned (default 500
frames): bullet count, mean speed (px/frame over each bullet's first 6 frames) and the most common bullet types
(+04). Bullet lines: frame slot type x y dx dy (BL dx/dy in px/frame; PS2 logs from tools/stage_compare are too,
older PS2 logs carried 8.8 values measured over one frame and show no speed).

    python3 research/phase14/compare_bullets.py bl_spawns.txt bl_bullets.txt ps2_spawns.txt ps2_bullets.txt [anchor]
"""
import collections
import math
import sys


def _speed(rows):
    v = [math.hypot(dx, dy) for *_, dx, dy in rows if dx or dy]
    return sum(v) / len(v) if v else 0.0


def main(bl_sp, bl_b, ps_sp, ps_b, B=500, anchor=54):
    anchor = str(anchor)
    a_bl = next(int(r[0]) for r in (l.split() for l in open(bl_sp)) if r[3] == anchor)
    a_ps = next(int(r[0]) for r in (l.split() for l in open(ps_sp)) if r[2] == anchor)
    blb = [(int(r[0]) - a_bl, int(r[2]), float(r[5]), float(r[6])) for r in (l.split() for l in open(bl_b))]
    psb = [(int(r[0]) - a_ps, int(r[2]), float(r[5]), float(r[6])) for r in (l.split() for l in open(ps_b))]
    span = max(f for f, *_ in blb)
    print("bin          BL n  spd  types                                | PS2 n  spd  types")
    for b in range(0, span + B, B):
        bb = [x for x in blb if b <= x[0] < b + B]
        pp = [x for x in psb if b <= x[0] < b + B]
        tb = collections.Counter(t for _, t, *_ in bb).most_common(3)
        tp = collections.Counter(t for _, t, *_ in pp).most_common(3)
        print(f"{b:5d}-{b + B:<6d} {len(bb):4d} {_speed(bb):4.2f} {str(tb):36} | {len(pp):4d} {_speed(pp):4.2f} {tp}")
    print("totals: BL", len(blb), "PS2", len([x for x in psb if 0 <= x[0] <= span]))


if __name__ == "__main__":
    args = sys.argv[1:5]
    main(*args, anchor=int(sys.argv[5]) if len(sys.argv) > 5 else 54)
