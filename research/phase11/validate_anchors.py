#!/usr/bin/env python3
"""Score Phase 11 function/RAM matching against address pairs documented in ibara360's comments.

ibara360's host sources describe many places as "ibara 0CXXXXXX ..., Kuro BL 0CYYYYYY".
Those were found by its author with live traces, independently of this matcher, so they are
a fair test set. Only the address pairs are extracted; no code is copied.

    python3 research/phase11/validate_anchors.py /path/to/ibara360 research/phase11/out
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

PAIR_RE = re.compile(r"ibara[^,;]{0,30}?(0C[0-9A-F]{6})[^.;]{0,40}?Kuro BL[^0-9]{0,12}(0C[0-9A-F]{6})")


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    root, out = Path(argv[0]), Path(argv[1])
    pairs = set()
    for p in list((root / "host").rglob("*.[ch]")) + list((root / "runtime").rglob("*.[ch]")):
        for m in PAIR_RE.finditer(p.read_text(errors="replace")):
            pairs.add((int(m.group(1), 16), int(m.group(2), 16)))

    fmap = {}
    func_starts_a = set()
    for r in csv.DictReader(open(out / "ibara_vs_ibarablk_functions.csv")):
        if r["a_addr"]:
            func_starts_a.add(int(r["a_addr"], 16))
        if r["a_addr"] and r["b_addr"]:
            fmap[int(r["a_addr"], 16)] = (int(r["b_addr"], 16), r["status"])
    rmap = {int(r["a_ram"], 16): int(r["b_ram"], 16) for r in csv.DictReader(open(out / "ibara_vs_ibarablk_ram_map.csv"))}

    results = []
    for a, b in sorted(pairs):
        if a in func_starts_a:
            got = fmap.get(a)
            verdict = "unmatched" if got is None else ("ok" if got[0] == b else f"MISMATCH->{got[0]:08X}")
            kind = "function"
        elif a >= 0x0C200000:
            got = rmap.get(a)
            verdict = "not_in_ram_map" if got is None else ("ok" if got == b else f"MISMATCH->{got:08X}")
            kind = "ram"
        else:
            kind, verdict = "code_inside_function", "not_scored"
        results.append({"ibara": f"{a:08X}", "kuro_bl": f"{b:08X}", "kind": kind, "verdict": verdict})

    scored = [r for r in results if r["verdict"] != "not_scored"]
    ok = sum(r["verdict"] == "ok" for r in scored)
    bad = [r for r in scored if r["verdict"].startswith("MISMATCH")]
    report = {"documented_pairs": len(results), "scored": len(scored), "ok": ok,
              "mismatches": len(bad), "results": results}
    (out / "anchor_validation.json").write_text(json.dumps(report, indent=1) + "\n")
    for r in results:
        print(f"{r['kind']:22} {r['ibara']} -> {r['kuro_bl']}  {r['verdict']}")
    print(f"\n{ok}/{len(scored)} scored anchors correct, {len(bad)} wrong")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
