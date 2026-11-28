#!/usr/bin/env python3
"""Compare the replay fixture's checkpoints and optional controller traces."""
import argparse
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from p2s_tools import load_ee

CP_BASE = 0x01FC0000
TRACE_BASE = 0x01AC0000
CP = struct.Struct("<8I")
TRACE = struct.Struct("<14I")
TRACE_FIELDS = (
    "scroll", "step", "cursor", "wait", "position", "animation", "kind", "active",
    "calls", "result", "spawn_tick", "spawn_scroll", "spawn_seed", "spawn_cursor",
)


def rows(mem, base, step, fmt, limit, side):
    return [fmt.unpack_from(mem, base + (side * step + i) * fmt.size) for i in range(limit)]


def first_difference(a, b, key_names):
    for i, (before, after) in enumerate(zip(a, b)):
        changes = {key: [f"{x:#x}", f"{y:#x}"] for key, x, y in zip(key_names, before, after) if x != y}
        if changes:
            return {"row": i, "changes": changes}
    return None


def analyze(mem, rp, controller):
    magic, mode, recorded, played, overflow, count_a, count_b, tick_miss = struct.unpack_from("<8I", mem, rp)
    if magic != 0x33504552 or mode != 1 or not 0 < recorded <= 20000 or played < recorded:
        raise ValueError("expected a completed record/playback capture")
    if overflow or min(count_a, count_b) < 1 or max(count_a, count_b) > 1400:
        raise ValueError("invalid checkpoint counts or replay overflow")
    a, b = (rows(mem, CP_BASE, 1400, CP, n, side) for side, n in enumerate((count_a, count_b)))
    before = {row[0]: row[1:] for row in a if row[0] < recorded}
    after = {row[0]: row[1:] for row in b if row[0] < recorded}
    if before.keys() != after.keys() or not before:
        raise ValueError("checkpoint coverage differs between recording and playback")
    keys = sorted(before)
    bad = [update for update in keys if before[update] != after[update]]
    fields = ("score", "rank", "stage_tick", "rng", "x", "y", "bombs")
    result = dict(recorded=recorded, played=played, compared=len(keys), tick_miss=tick_miss,
                  mismatches=len(bad), first_checkpoint=bad[0] if bad else None,
                  first_by_field={name: next((i for i in bad if before[i][idx] != after[i][idx]), None)
                                  for idx, name in enumerate(fields)})
    if controller:
        limit = min(1200, recorded)
        a, b = (rows(mem, TRACE_BASE, 1200, TRACE, limit, side) for side in range(2))
        result["stage_clock"] = first_difference([r[:4] for r in a], [r[:4] for r in b], TRACE_FIELDS[:4])
        result["slot_3"] = first_difference([r[4:8] for r in a], [r[4:8] for r in b], TRACE_FIELDS[4:8])
        result["factory"] = [
            [dict(update=i, **dict(zip(TRACE_FIELDS[8:], row[8:]))) for i, row in enumerate(side) if row[8]]
            for side in (a, b)
        ]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state", type=Path)
    parser.add_argument("symbols", type=Path)
    parser.add_argument("--controller-trace", action="store_true")
    args = parser.parse_args()
    rp = json.loads(args.symbols.read_text())["rp"]
    print(json.dumps(analyze(load_ee(args.state), rp, args.controller_trace), indent=2))


if __name__ == "__main__":
    main()
