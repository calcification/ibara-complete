#!/usr/bin/env python3
"""Phase 14: compare BL (MAME) and PS2 (PCSX2) stage enemy-spawn logs per enemy type.

Inputs are the text logs written by research/phase13/spawn_log.lua (BL) and the PS2 spawn logger
(ps2/hooks/spawnlog.c, decoded from a savestate). Both use the arcade enemy-type numbering (+04), which the
PS2 port kept. Logs are aligned at the first spawn of --anchor-type; only BL's --stage records are used and the
PS2 window has the same frame span. Output: per type, spawn counts, median spawn interval, subtypes, HP/score
values at spawn, so BL's stage changes can be ported type by type.

    python3 research/phase14/compare_spawns.py bl_spawns.txt ps2_spawns.txt --stage 2 --anchor-type 54
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics
import sys


def load_bl(path, stage):
    out = []
    for line in open(path):
        f = line.split()
        if int(f[1]) != stage:
            continue
        out.append({"frame": int(f[0]), "type": int(f[3]), "sub": int(f[4], 16), "hp": int(f[5]), "score": int(f[6]),
                    "x": int(f[7]), "y": int(f[8])})
    return out


def load_ps2(path):
    out = []
    for line in open(path):
        f = line.split()
        out.append({"frame": int(f[0]), "type": int(f[2]), "sub": int(f[3], 16), "hp": int(f[4]), "score": int(f[5]),
                    "x": int(f[6]), "y": int(f[7])})
    return out


def align(recs, anchor):
    t0 = next(r["frame"] for r in recs if r["type"] == anchor)
    return [dict(r, frame=r["frame"] - t0) for r in recs if r["frame"] >= t0]


def summary(recs):
    by = collections.defaultdict(list)
    for r in recs:
        by[r["type"]].append(r)
    out = {}
    for t, rs in by.items():
        fr = sorted(r["frame"] for r in rs)
        gaps = [b - a for a, b in zip(fr, fr[1:]) if b > a]
        out[t] = {
            "count": len(rs), "first": fr[0], "last": fr[-1],
            "median_gap": statistics.median(gaps) if gaps else None,
            "subtypes": dict(collections.Counter(f"{r['sub']:X}" for r in rs).most_common(4)),
            "hp": dict(collections.Counter(r["hp"] for r in rs).most_common(3)),
            "score": dict(collections.Counter(r["score"] for r in rs).most_common(3)),
        }
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bl")
    ap.add_argument("ps2")
    ap.add_argument("--stage", type=int, default=2, help="BL stage byte (2 = stage 1)")
    ap.add_argument("--anchor-type", type=int, default=54)
    ap.add_argument("--retained-start", type=int, help="first retained PS2 frame after a ring wrap")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    bl = align(load_bl(a.bl, a.stage), a.anchor_type)
    span = bl[-1]["frame"]
    ps_raw = load_ps2(a.ps2)
    ps = align(ps_raw, a.anchor_type)
    lower = 0
    if a.retained_start is not None:
        ps_anchor = next(r["frame"] for r in ps_raw if r["type"] == a.anchor_type)
        lower = max(0, a.retained_start - ps_anchor + 1)
        span = min(span, ps[-1]["frame"])
        print(f"Wrapped capture: shared spawn window [{lower}, {span}] after the anchor.")
    bl = [r for r in bl if lower <= r["frame"] <= span]
    ps = [r for r in ps if lower <= r["frame"] <= span]
    sb, sp = summary(bl), summary(ps)
    rows = []
    for t in sorted(set(sb) | set(sp), key=lambda t: min(sb.get(t, {"first": 1e9})["first"], sp.get(t, {"first": 1e9})["first"])):
        b, p = sb.get(t), sp.get(t)
        rows.append({"type": t, "bl": b, "ps2": p})
        def fmt(s):
            if not s:
                return "-"
            return (f"n={s['count']:3d} first={s['first']:5d} gap={s['median_gap']} sub={s['subtypes']} "
                    f"hp={s['hp']} score={s['score']}")
        flag = "" if (b and p and b["count"] == p["count"] and b["subtypes"] == p["subtypes"]) else "  <-- differs"
        print(f"type {t:3d}{flag}\n   BL : {fmt(b)}\n   PS2: {fmt(p)}")
    print(f"\nAligned frames {lower}–{span}; BL spawns {len(bl)}, PS2 spawns {len(ps)}")
    if a.json:
        json.dump({"span": span, "types": rows}, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    sys.exit(main())
