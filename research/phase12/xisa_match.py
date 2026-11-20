#!/usr/bin/env python3
"""Phase 12: propose PS2 EE counterparts for arcade Ibara SH-3 routines (esp. those Black Label changed).

The PS2 port reuses the arcade's structures (shot stride 0x50, bullet stride 0x54, 2^24 rank), so a routine
and its port tend to share distinctive constants and the game structures they touch. Score per pair:
    0.60 * idf-weighted Jaccard of constants
  + 0.25 * Jaccard of referenced structures (player, rank, shots, bullets, ...)
  + 0.15 * size agreement (after the global MIPS/SH-3 instruction ratio)
then greedy mutual-best assignment, then call-graph propagation from accepted pairs and --anchor seeds.
Output is a candidate list for debugger confirmation, NOT verified correspondences.

    python3 research/phase12/xisa_match.py /path/to/ibara360 SLPM_663.01 --out research/phase12/out \
        [--anchor 0C062550=0012XXXX ...]
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "phase11"))
import mips_funcs  # noqa: E402

# Structures present in both programs: (tag, base, size). Arcade Ibara addresses from ibara360 notes,
# PS2 from this repository's static phases (06-10).
ARCADE_STRUCTS = [
    ("player", 0x0C283794, 2 * 0x280), ("rank", 0x0C27DFF8, 4), ("shots", 0x0C217A04, 2 * 0x2800),
    ("bullets", 0x0C27E0FC, 256 * 0x54), ("enemies", 0x0C26CD40, 192 * 0xB4),
]
PS2_STRUCTS = [
    ("player", 0x0044C380, 2 * 0x290), ("rank", 0x00338EB4, 4), ("shots", 0x0044EA40, 2 * 0x2800),
    ("bullets", 0x00462F40, 256 * 0x54),
]
# Strides/sizes that differ only because the record layouts differ: normalise to a shared token.
EQUIV = {0x280: "STRIDE_PLAYER", 0x290: "STRIDE_PLAYER", 0x2A0: "STRIDE_PLAYER"}


def tags_for(refs, table) -> set[str]:
    out = set()
    for r in refs:
        for name, base, size in table:
            if base <= r < base + size:
                out.add(name)
    return out


def norm_consts(vals) -> set:
    out = set()
    for v in vals:
        v &= 0xFFFFFFFF
        sv = v - (1 << 32) if v & 0x80000000 else v
        if -16 <= sv <= 16:
            continue
        if 0x0C000000 <= v < 0x0D000000:
            continue  # arcade addresses are not portable (PS2 addresses are split off by mips_funcs)
        out.add(EQUIV.get(v, v))
    return out


class Side:
    def __init__(self, sizes: dict[int, int], consts: dict[int, set], tags: dict[int, set], calls: dict[int, list[int]]):
        self.sizes, self.consts, self.tags, self.calls = sizes, consts, tags, calls


def score_all(A: Side, P: Side, ratio: float, min_score: float = 0.30):
    df = collections.Counter()
    for side in (A, P):
        for cs in side.consts.values():
            df.update(cs)
    n = len(A.consts) + len(P.consts)
    idf = {v: math.log(n / c) for v, c in df.items()}
    index = collections.defaultdict(list)
    for p, cs in P.consts.items():
        for v in cs:
            if df[v] <= 40:  # very common constants carry no identity
                index[v].append(p)
    tag_index = collections.defaultdict(list)
    for p, ts in P.tags.items():
        for t in ts:
            tag_index[t].append(p)
    scores = {}
    for a, ca in A.consts.items():
        cands = set()
        for v in ca:
            cands.update(index.get(v, ()))
        if not cands and A.tags.get(a):
            for t in A.tags[a]:
                cands.update(tag_index[t])
        for p in cands:
            cp = P.consts[p]
            inter = sum(idf[v] for v in ca & cp)
            union = sum(idf[v] for v in ca | cp) or 1.0
            ta, tp = A.tags.get(a, set()), P.tags.get(p, set())
            tj = len(ta & tp) / len(ta | tp) if ta | tp else 0.0
            la, lp = A.sizes[a] * ratio, P.sizes[p]
            sz = min(la, lp) / max(la, lp) if la and lp else 0.0
            s = 0.60 * inter / union + 0.25 * tj + 0.15 * sz
            if s >= min_score:
                scores[(a, p)] = s
    return scores


def assign(scores: dict, A: Side, P: Side, anchors: dict[int, int]):
    pairs = {a: (p, "anchor", 1.0) for a, p in anchors.items()}
    used = set(anchors.values())
    best_a, best_p = {}, {}
    for (a, p), s in scores.items():
        if s > best_a.get(a, (None, -1))[1]:
            best_a[a] = (p, s)
        if s > best_p.get(p, (None, -1))[1]:
            best_p[p] = (a, s)
    for a, (p, s) in sorted(best_a.items(), key=lambda kv: -kv[1][1]):
        if a in pairs or p in used:
            continue
        if best_p[p][0] == a:
            pairs[a] = (p, "mutual_best", s)
            used.add(p)
    changed = True
    while changed:
        changed = False
        for a, (p, _m, _s) in list(pairs.items()):
            ca, cp = A.calls.get(a, []), P.calls.get(p, [])
            if not ca or len(ca) != len(cp):
                continue
            for x, y in zip(ca, cp):
                if x in A.sizes and y in P.sizes and x not in pairs and y not in used:
                    pairs[x] = (y, "callgraph", scores.get((x, y), 0.0))
                    used.add(y)
                    changed = True
    return pairs


def main(argv=None) -> int:
    from sh3_drc_diff import load_program  # phase11

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ibara360", type=Path)
    ap.add_argument("elf", type=Path, help="retail SLPM_663.01 (or a path to the extracted ELF)")
    ap.add_argument("--out", type=Path, default=HERE / "out")
    ap.add_argument("--anchor", action="append", default=[], help="SH3=PS2 hex pair known to correspond")
    ap.add_argument("--phase11", type=Path, default=HERE.parent / "phase11" / "out" / "ibara_vs_ibarablk_functions.csv")
    args = ap.parse_args(argv)

    arc = load_program(args.ibara360 / "gen" / "ibara_drc")
    segs = mips_funcs.load_elf(args.elf)
    mf, gp = mips_funcs.extract(segs, {mips_funcs.elf_entry(args.elf)}, gp=mips_funcs.elf_gp(args.elf))

    A = Side({a: len(f.insns) for a, f in arc.items()},
             {a: norm_consts(f.consts) for a, f in arc.items()},
             {a: tags_for(f.ram_refs, ARCADE_STRUCTS) for a, f in arc.items()},
             {a: f.calls for a, f in arc.items()})
    P = Side({a: f.n_insns for a, f in mf.items()},
             {a: norm_consts(f.consts + f.mem_offsets) for a, f in mf.items()},
             {a: tags_for(f.data_refs, PS2_STRUCTS) for a, f in mf.items()},
             {a: f.calls for a, f in mf.items()})
    anchors = {int(x, 16): int(y, 16) for x, y in (s.split("=") for s in args.anchor)}
    # PS2 ELF also holds libraries/renderer, so a global size ratio would be skewed: use anchors if any.
    rs = sorted(P.sizes[p] / A.sizes[a] for a, p in anchors.items() if A.sizes.get(a) and P.sizes.get(p))
    ratio = rs[len(rs) // 2] if rs else 1.0
    scores = score_all(A, P, ratio)
    pairs = assign(scores, A, P, anchors)

    status = {}
    if args.phase11.exists():
        for r in csv.DictReader(open(args.phase11)):
            if r["a_addr"]:
                status[int(r["a_addr"], 16)] = (r["status"], r["b_addr"])
    args.out.mkdir(parents=True, exist_ok=True)
    with open(args.out / "arcade_to_ps2.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["arcade_addr", "ps2_addr", "method", "score", "bl_status", "bl_addr", "arcade_insns", "ps2_insns"])
        for a in sorted(arc):
            p, m, s = pairs.get(a, (None, "", 0.0))
            st, bl = status.get(a, ("", ""))
            w.writerow([f"{a:08X}", f"{p:08X}" if p is not None else "", m, f"{s:.3f}", st, bl, A.sizes[a],
                        P.sizes.get(p, "") if p is not None else ""])
    changed = [a for a, (st, _b) in status.items() if st in ("changed", "operands", "a_only")]
    summary = {
        "ps2_functions": len(mf), "ps2_gp": f"{gp:08X}" if gp is not None else None,
        "arcade_functions": len(arc), "size_ratio_mips_per_sh3": round(ratio, 3),
        "matched": len(pairs), "by_method": dict(collections.Counter(m for _p, m, _s in pairs.values())),
        "bl_changed_arcade_routines": len(changed),
        "bl_changed_with_ps2_candidate": sum(1 for a in changed if a in pairs),
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
