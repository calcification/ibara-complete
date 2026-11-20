#!/usr/bin/env python3
"""Phase 11: structural diff of arcade Ibara vs Ibara Kuro Black Label SH-3 programs.

Input is a LOCAL checkout of the public ibara360 project (not bundled here; it has no
license file, so none of its code is copied into this repository). We only read the
per-instruction annotations its recompiler emits (``/* 0CXXXXXX mnemonic */``) plus the
C statement on the same line, and emit addresses, hashes and metrics.

Goal: enumerate exactly which arcade routines Black Label changed, added or removed,
so the PS2 port can be planned as "PS2 native mode + measured BL delta" instead of
guessing.

Usage:
    python3 research/phase11/sh3_drc_diff.py /path/to/ibara360 --out research/phase11/out
    python3 research/phase11/sh3_drc_diff.py /path/to/ibara360 --a ibara_drc --b ibaraarr_drc ...
"""
from __future__ import annotations

import argparse
import collections
import csv
import difflib
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

FUNC_RE = re.compile(r"^void (?:[a-z]+_)?f_(0C[0-9A-F]{6})\(sh3_t \*c\)\s*$")
INSN_RE = re.compile(r"/\* (0C[0-9A-F]{6}) ([a-z][a-z0-9./]*)[^*]*\*/")
CALL_RE = re.compile(r"CALL[A-Z]*\([^,]*,\s*(?:[a-z]+_)?f_(0C[0-9A-F]{6})")
HEX_RE = re.compile(r"0x([0-9A-Fa-f]+)u?")
LABEL_RE = re.compile(r"L_0C[0-9A-F]{6}")
NOISE_RE = re.compile(r"\b(UPD|IF|BLKS)\([^;]*?\);\s*")

# Arcade CV1000 map (ibara360 runtime): 0C000000.. program (U4 copy), work RAM above it.
PROGRAM_END_GUESS = 0x0C200000


@dataclass
class Insn:
    addr: int
    mnem: str
    text: str  # normalized C statement


@dataclass
class Func:
    addr: int
    insns: list[Insn] = field(default_factory=list)
    calls: list[int] = field(default_factory=list)
    consts: list[int] = field(default_factory=list)   # small literals
    ram_refs: list[int] = field(default_factory=list)  # 0C2xxxxx-ish data addresses
    code_refs: list[int] = field(default_factory=list)

    @property
    def mnems(self) -> tuple[str, ...]:
        return tuple(i.mnem for i in self.insns)

    def h_loose(self) -> str:
        return hashlib.sha1("|".join(self.mnems).encode()).hexdigest()

    def h_strict(self) -> str:
        return hashlib.sha1("\n".join(f"{i.mnem}:{i.text}" for i in self.insns).encode()).hexdigest()


def classify_hex(v: int) -> str:
    if 0x0C000000 <= v < 0x0D000000:
        return "code" if v < PROGRAM_END_GUESS else "ram"
    return "const"


def normalize(stmt: str, f: Func) -> str:
    stmt = NOISE_RE.sub("", stmt)
    stmt = LABEL_RE.sub("L", stmt)
    stmt = re.sub(r"(?:[a-z]+_)?f_0C[0-9A-F]{6}", "F", stmt)

    def sub(m: re.Match) -> str:
        v = int(m.group(1), 16)
        kind = classify_hex(v)
        if kind == "code":
            f.code_refs.append(v)
            return "CODE"
        if kind == "ram":
            f.ram_refs.append(v)
            return "RAM"
        f.consts.append(v)
        return m.group(0)

    stmt = HEX_RE.sub(sub, stmt)
    return " ".join(stmt.split())


def load_program(root: Path) -> dict[int, Func]:
    funcs: dict[int, Func] = {}
    files = sorted(p for p in root.glob("*recomp_[0-9]*.c"))
    if not files:
        raise SystemExit(f"no recomp_NN.c files in {root}")
    for path in files:
        cur: Func | None = None
        for line in path.read_text(errors="replace").splitlines():
            m = FUNC_RE.match(line)
            if m:
                cur = Func(int(m.group(1), 16))
                funcs[cur.addr] = cur
                continue
            if cur is None:
                continue
            for cm in CALL_RE.finditer(line):
                cur.calls.append(int(cm.group(1), 16))
            im = INSN_RE.search(line)
            if im:
                stmt = line[: im.start()]
                cur.insns.append(Insn(int(im.group(1), 16), im.group(2), normalize(stmt, cur)))
    for f in funcs.values():
        f.insns.sort(key=lambda i: i.addr)
    return funcs


def unique_index(funcs: dict[int, Func], key) -> dict[str, int]:
    buckets: dict[str, list[int]] = collections.defaultdict(list)
    for a, f in funcs.items():
        if f.insns:
            buckets[key(f)].append(a)
    return {h: v[0] for h, v in buckets.items() if len(v) == 1}


def match(A: dict[int, Func], B: dict[int, Func]) -> dict[int, tuple[int, str, float]]:
    """Return {a_addr: (b_addr, method, similarity)}."""
    pairs: dict[int, tuple[int, str, float]] = {}
    used_b: set[int] = set()

    for method, key in (("strict", Func.h_strict), ("loose", Func.h_loose)):
        ia, ib = unique_index(A, key), unique_index(B, key)
        for h, a in ia.items():
            if a in pairs:
                continue
            b = ib.get(h)
            if b is not None and b not in used_b:
                pairs[a] = (b, method, 1.0)
                used_b.add(b)

    # Call-graph propagation: if matched a->b, align their callee lists positionally.
    changed = True
    while changed:
        changed = False
        for a, (b, _, _) in list(pairs.items()):
            ca, cb = A[a].calls, B[b].calls
            if len(ca) != len(cb):
                continue
            for x, y in zip(ca, cb):
                if x in A and y in B and x not in pairs and y not in used_b:
                    sim = difflib.SequenceMatcher(None, A[x].mnems, B[y].mnems, autojunk=False).ratio()
                    if sim >= 0.5:
                        pairs[x] = (y, "callgraph", sim)
                        used_b.add(y)
                        changed = True

    # Order-preserving gap fill between anchors.
    a_sorted = sorted(A)
    b_sorted = sorted(B)
    b_pos = {b: i for i, b in enumerate(b_sorted)}
    anchors = sorted((a, pairs[a][0]) for a in pairs)
    anchors = [(None, None)] + anchors + [(None, None)]
    a_pos = {a: i for i, a in enumerate(a_sorted)}
    for (a0, b0), (a1, b1) in zip(anchors, anchors[1:]):
        ia0 = -1 if a0 is None else a_pos[a0]
        ia1 = len(a_sorted) if a1 is None else a_pos[a1]
        ib0 = -1 if b0 is None else b_pos[b0]
        ib1 = len(b_sorted) if b1 is None else b_pos[b1]
        if ib1 <= ib0:
            continue
        ga = [x for x in a_sorted[ia0 + 1: ia1] if x not in pairs]
        gb = [y for y in b_sorted[ib0 + 1: ib1] if y not in used_b]
        if not ga or not gb or len(ga) * len(gb) > 4000:
            continue
        cands = []
        for x in ga:
            for y in gb:
                sim = difflib.SequenceMatcher(None, A[x].mnems, B[y].mnems, autojunk=False).ratio()
                if sim >= 0.55:
                    cands.append((sim, x, y))
        for sim, x, y in sorted(cands, reverse=True):
            if x in pairs or y in used_b:
                continue
            pairs[x] = (y, "gapfill", sim)
            used_b.add(y)

    # Global last pass for leftovers (functions that moved out of order or were rewritten).
    ra = [x for x in A if x not in pairs and A[x].insns]
    rb = [y for y in B if y not in used_b and B[y].insns]
    cands = []
    for x in ra:
        la = len(A[x].insns)
        for y in rb:
            lb = len(B[y].insns)
            if not (0.5 <= la / lb <= 2.0):
                continue
            sm = difflib.SequenceMatcher(None, A[x].mnems, B[y].mnems, autojunk=False)
            if sm.real_quick_ratio() < 0.6 or sm.quick_ratio() < 0.6:
                continue
            sim = sm.ratio()
            if sim >= 0.6:
                cands.append((sim, x, y))
    for sim, x, y in sorted(cands, reverse=True):
        if x in pairs or y in used_b:
            continue
        pairs[x] = (y, "global", sim)
        used_b.add(y)
    return pairs


def opcode_diff(fa: Func, fb: Func) -> dict:
    sm = difflib.SequenceMatcher(None, fa.mnems, fb.mnems, autojunk=False)
    ops = collections.Counter()
    hunks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        ops[tag] += max(i2 - i1, j2 - j1)
        if len(hunks) < 12:
            hunks.append({
                "tag": tag,
                "a": f"{fa.insns[i1].addr:08X}" if i1 < len(fa.insns) else None,
                "b": f"{fb.insns[j1].addr:08X}" if j1 < len(fb.insns) else None,
                "a_len": i2 - i1,
                "b_len": j2 - j1,
                "a_mnems": " ".join(fa.mnems[i1:i2][:10]),
                "b_mnems": " ".join(fb.mnems[j1:j2][:10]),
            })
    const_only = []
    if fa.mnems == fb.mnems:
        for ia, ib in zip(fa.insns, fb.insns):
            if ia.text != ib.text:
                # Record only the literal values that differ (ROM facts), never the generated C text.
                va = [v for v in HEX_RE.findall(ia.text)]
                vb = [v for v in HEX_RE.findall(ib.text)]
                const_only.append({"a": f"{ia.addr:08X}", "b": f"{ib.addr:08X}", "mnem": ia.mnem,
                                   "a_values": ["0x" + v.upper() for v in va],
                                   "b_values": ["0x" + v.upper() for v in vb],
                                   "register_or_form_change": va == vb})
    return {"ops": dict(ops), "hunks": hunks, "operand_changes": const_only[:40],
            "n_operand_changes": len(const_only)}


def ram_map(A, B, pairs) -> list[tuple[int, int, int]]:
    """Map data addresses A->B via aligned instructions of identical-shape matched funcs."""
    votes: dict[int, collections.Counter] = collections.defaultdict(collections.Counter)
    for a, (b, _, _) in pairs.items():
        fa, fb = A[a], B[b]
        if fa.mnems != fb.mnems:
            continue
        # positional zip of collected ram_refs is valid only when counts match
        if len(fa.ram_refs) == len(fb.ram_refs):
            for x, y in zip(fa.ram_refs, fb.ram_refs):
                votes[x][y] += 1
    out = []
    for x, c in sorted(votes.items()):
        y, n = c.most_common(1)[0]
        out.append((x, y, n))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ibara360", type=Path, help="local ibara360 checkout")
    ap.add_argument("--a", default="ibara_drc", help="baseline program dir under gen/ (default ibara_drc)")
    ap.add_argument("--b", default="ibarablk_drc", help="compared program dir under gen/ (default ibarablk_drc)")
    ap.add_argument("--out", type=Path, default=Path("research/phase11/out"))
    args = ap.parse_args(argv)

    A = load_program(args.ibara360 / "gen" / args.a)
    B = load_program(args.ibara360 / "gen" / args.b)
    pairs = match(A, B)
    args.out.mkdir(parents=True, exist_ok=True)
    tag = f"{args.a.replace('_drc', '')}_vs_{args.b.replace('_drc', '')}"

    rows = []
    details = {}
    matched_b = {b for b, _, _ in pairs.values()}
    for a in sorted(A):
        fa = A[a]
        if a in pairs:
            b, method, sim = pairs[a]
            fb = B[b]
            if fa.h_strict() == fb.h_strict():
                status = "identical"
            elif fa.mnems == fb.mnems:
                status = "operands"
            else:
                status = "changed"
            sim2 = sim if status != "changed" else difflib.SequenceMatcher(None, fa.mnems, fb.mnems, autojunk=False).ratio()
            rows.append([f"{a:08X}", f"{b:08X}", status, method, f"{sim2:.3f}", len(fa.insns), len(fb.insns)])
            if status != "identical":
                details[f"{a:08X}->{b:08X}"] = {"status": status, "sim": round(sim2, 3), **opcode_diff(fa, fb)}
        else:
            rows.append([f"{a:08X}", "", "a_only", "", "", len(fa.insns), ""])
    for b in sorted(B):
        if b not in matched_b:
            rows.append(["", f"{b:08X}", "b_only", "", "", "", len(B[b].insns)])

    with open(args.out / f"{tag}_functions.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["a_addr", "b_addr", "status", "method", "mnemonic_similarity", "a_insns", "b_insns"])
        w.writerows(rows)

    rm = ram_map(A, B, pairs)
    with open(args.out / f"{tag}_ram_map.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["a_ram", "b_ram", "votes"])
        for x, y, n in rm:
            w.writerow([f"{x:08X}", f"{y:08X}", n])

    counts = collections.Counter(r[2] for r in rows)
    ins_changed = sum(int(r[5] or 0) for r in rows if r[2] in ("changed", "a_only"))
    b_only_ins = sum(int(r[6] or 0) for r in rows if r[2] == "b_only")
    summary = {
        "a": args.a, "b": args.b,
        "a_functions": len(A), "b_functions": len(B),
        "a_instructions": sum(len(f.insns) for f in A.values()),
        "b_instructions": sum(len(f.insns) for f in B.values()),
        "status_counts": dict(counts),
        "a_instructions_in_changed_or_removed": ins_changed,
        "b_instructions_in_added": b_only_ins,
        "ram_addresses_mapped": len(rm),
    }
    (args.out / f"{tag}_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (args.out / f"{tag}_details.json").write_text(json.dumps(details, indent=1) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
