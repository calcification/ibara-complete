#!/usr/bin/env python3
"""Tag Black Label's changed / added SH-3 routines by the game structures they reference.

Reads the Phase 11 function diff CSV plus the local ibara360 recompiled sources, and for every
Black Label function that is new or differs from arcade Ibara, lists which known work-RAM
structures its literal pool references. The structure table below is our own summary of
addresses documented in ibara360's comments (big-endian SH-3 view); sizes are from those notes.

    python3 research/phase11/tag_subsystems.py /path/to/ibara360 research/phase11/out
"""
from __future__ import annotations

import collections
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sh3_drc_diff import load_program  # noqa: E402

# (name, base, size) in Black Label's address space.
BL_STRUCTS = [
    ("player_records", 0x0C29D1D8, 2 * 0x2A0),
    ("weapon_stock", 0x0C22E028, 7 * 4),
    ("rank", 0x0C297A3C, 4),
    ("enemy_parts", 0x0C286578, 192 * 0xB4),
    ("enemy_bullets", 0x0C297B40, 256 * 0x54),
    ("player_shots", 0x0C229004, 2 * 0x2800),
    ("item_drop_cycle", 0x0C28F608, 1),
    ("pickup_streaks", 0x0C22E2AC, 16),
    ("attract_flag", 0x0C22E015, 1),
    ("next_medal", 0x0C3C53E0, 1),
    ("bgm_seq", 0x0C3C4018, 1),
    ("game_on", 0x0C2A6D90, 4),
    ("ship_select_flag", 0x0C3C86AC, 4),
    ("stage", 0x0C3C4170, 1),
    ("camera", 0x0C3C4048, 4),
    ("layers", 0x0C286318, 8 * 0x4C),
    ("stage_record_id", 0x0C23E0A6, 2),
]


def tag(addr: int) -> str | None:
    for name, base, size in BL_STRUCTS:
        if base <= addr < base + size:
            return name
    return None


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    root, out = Path(argv[0]), Path(argv[1])
    B = load_program(root / "gen" / "ibarablk_drc")
    rows = list(csv.DictReader(open(out / "ibara_vs_ibarablk_functions.csv")))
    report = []
    per_tag = collections.defaultdict(list)
    for r in rows:
        if r["status"] not in ("changed", "operands", "b_only") or not r["b_addr"]:
            continue
        b = int(r["b_addr"], 16)
        f = B[b]
        tags = collections.Counter(t for t in (tag(x) for x in f.ram_refs) if t)
        entry = {
            "bl": r["b_addr"], "ibara": r["a_addr"] or None, "status": r["status"],
            "similarity": r["mnemonic_similarity"] or None,
            "low_confidence": bool(r["mnemonic_similarity"]) and float(r["mnemonic_similarity"]) < 0.65,
            "insns": len(f.insns), "tags": dict(tags), "calls": len(f.calls),
        }
        report.append(entry)
        for t in tags:
            per_tag[t].append(r["b_addr"])
        if not tags:
            per_tag["untagged"].append(r["b_addr"])

    summary = {t: {"functions": len(v), "bl_addrs": sorted(v)} for t, v in sorted(per_tag.items(), key=lambda kv: -len(kv[1]))}
    (out / "bl_delta_tagged.json").write_text(json.dumps({"by_subsystem": summary, "functions": report}, indent=1) + "\n")
    with open(out / "bl_delta_tagged.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["bl_addr", "ibara_addr", "status", "similarity", "low_confidence", "insns", "tags"])
        for e in report:
            w.writerow([e["bl"], e["ibara"] or "", e["status"], e["similarity"] or "", int(e["low_confidence"]),
                        e["insns"], ";".join(f"{k}:{v}" for k, v in sorted(e["tags"].items()))])
    for t, v in summary.items():
        print(f"{t:18} {v['functions']:4d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
