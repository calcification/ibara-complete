#!/usr/bin/env python3
"""Compare enemy part-record tables (score, base HP) between Black Label and PS2; emit BLACK LABEL HP patches.

Each enemy part points (+0x10) at a table of 16-byte records indexed by its record number. PS2 records hold the
score at +4 and the base HP at +0xC (little-endian s16); BL records hold the score at +4 and the base HP at +0xE
(big-endian). The stage loggers list every table they saw (BL with its contents, PS2 the address only); this
tool reads the PS2 tables from the retail executable, pairs each PS2 table with the BL table of the same enemy
type whose score column matches best, and reports entries whose HP differs.

    python3 tools/stage_compare/diff_part_tables.py 'Ibara (Japan).iso' runs/stage2 [runs/stage3 ...] [--write]

--write merges the HP differences into ps2/bl_part_hp.json (applied to the BLACK LABEL build by
scripts/build_ee_hooks.py as preimage-checked word patches). Only entries whose score matches are patched;
score mismatches are listed for manual review. The JSON holds addresses and small numbers only.
"""
from __future__ import annotations

import argparse
import collections
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import build_pnach  # noqa: E402

OUT = ROOT / "ps2" / "bl_part_hp.json"
ENTRIES = 128


def ps2_word(elf: bytes, addr: int) -> int:
    return struct.unpack_from("<I", elf, addr - build_pnach.ELF_BASE + build_pnach.ELF_FILE_OFFSET)[0]


def load_runs(dirs):
    bl = collections.defaultdict(dict)    # type -> table -> [(score, hp)]
    ps = collections.defaultdict(set)     # type -> {table}
    for d in dirs:
        for line in open(d / "bl_tables.txt"):
            t, tb, k, score, hp = line.split()
            bl[int(t)].setdefault(tb, [None] * ENTRIES)[int(k)] = (int(score), int(hp))
        for line in open(d / "ps2_tables.txt"):
            t, tb = line.split()
            ps[int(t)].add(int(tb, 16))
    return bl, ps


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("retail_iso", type=Path)
    ap.add_argument("runs", type=Path, nargs="+")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    elf = build_pnach.load_elf(a.retail_iso)
    end = build_pnach.ELF_BASE + len(elf) - build_pnach.ELF_FILE_OFFSET
    bl, ps = load_runs(a.runs)
    patches, review = {}, []
    for t in sorted(ps):
        for ptab in sorted(ps[t]):
            if not build_pnach.ELF_BASE <= ptab < end - 16 * ENTRIES:
                review.append(f"type {t}: PS2 table {ptab:08X} outside the executable image")
                continue
            prec = [(ps2_word(elf, ptab + 16 * k + 4), ps2_word(elf, ptab + 16 * k + 12)) for k in range(ENTRIES)]
            best, score = None, -1
            for btab, brec in bl.get(t, {}).items():
                s = sum(1 for k in range(ENTRIES) if brec[k] and brec[k][0] == prec[k][0] and prec[k][0])
                if s > score:
                    best, score = btab, s
            if best is None:
                review.append(f"type {t}: PS2 table {ptab:08X} has no BL table (type not seen in the BL run)")
                continue
            brec = bl[t][best]
            n = 0
            for k in range(ENTRIES):
                if not brec[k]:
                    continue
                pscore, pword = prec[k]
                bscore, bhp = brec[k]
                php = struct.unpack("<h", struct.pack("<H", pword & 0xFFFF))[0]
                if pscore == 0 and bscore == 0 and php == 0:
                    continue
                if pscore != bscore:
                    if pscore and bscore:
                        review.append(f"type {t} table {ptab:08X} entry {k:02X}: score PS2 {pscore} vs BL {bscore}")
                    continue
                if php != bhp:
                    addr = ptab + 16 * k + 12
                    patches[f"{addr:08X}"] = {"orig": f"{pword:08X}",
                                              "new": f"{(pword & 0xFFFF0000) | (bhp & 0xFFFF):08X}",
                                              "type": t, "entry": k, "ps2_hp": php, "bl_hp": bhp}
                    n += 1
            print(f"type {t:3d} PS2 {ptab:08X} ~ BL {best} ({score} matching scores): {n} HP differences")
    for r in review:
        print("REVIEW:", r)
    for addr, p in sorted(patches.items()):
        print(f"  {addr}: type {p['type']} entry {p['entry']:02X} HP {p['ps2_hp']} -> {p['bl_hp']}")
    if a.write:
        cur = json.loads(OUT.read_text()) if OUT.exists() else {}
        cur.update(patches)
        OUT.write_text(json.dumps(dict(sorted(cur.items())), indent=1) + "\n")
        print(f"wrote {len(cur)} patches to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
