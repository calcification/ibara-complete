#!/usr/bin/env python3
"""Summarize Stage 6 type-14 write traces and paired PCSX2 probe saves."""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/stage_compare"))
from run_stage import read_ps2_log
from p2s_tools import load_ee

ROSE_CALLERS = {0x0C0A2C4C, 0x0C0A2EB2, 0x0C0A316E}
ROSE_PATTERN_CURSOR = "0C189CA0"


def trace(path):
    callers = defaultdict(list)
    with path.open() as source:
        for line in source:
            if line.startswith("f="):
                fields = dict(token.split("=", 1) for token in line.split())
                if "caller" in fields:
                    callers[int(fields["caller"], 16)].append(fields)
    print("Return PC   Type-14 writes   Rose pattern   First frame   Last frame")
    for pc, writes in sorted(callers.items()):
        roses = sum(w.get("R10") == ROSE_PATTERN_CURSOR for w in writes)
        print(f"{pc:08X}    {len(writes):>14} {roses:>14} {writes[0]['f']:>13} {writes[-1]['f']:>12}")
    print("Confirmed rose-path writes:", sum(
        w.get("R10") == ROSE_PATTERN_CURSOR for pc in ROSE_CALLERS for w in callers[pc]
    ))


def core_timing(records, subtype):
    rows = [row for row in records if row[3] == subtype and row[-2] == 7]
    if not rows or len({row[1] & 0xFF for row in rows}) != 1:
        raise ValueError(f"missing or ambiguous stage-6 core subtype {subtype}")
    start = next((row[-1] for row in rows if row[2] > 0), None)
    if start is None:
        raise ValueError(f"core {subtype} has no positive HP sample")
    end = next((row[-1] for row in rows if row[-1] >= start and not row[2]), None)
    return start, end, end - start if end is not None else None


def report_mame_run(directory):
    with (directory / "core.txt").open() as source:
        # Normalize the MAME stage-relative clock to the format used by core_timing.
        records = []
        for line in source:
            frame, slot, hp, subtype, *_ = line.split()
            records.append((0, int(slot), int(hp), int(subtype, 16), 7, int(frame)))
    first_core = core_timing(records, 0)
    rose_core = core_timing(records, 2)
    with (directory / "spawns.txt").open() as source:
        roses = sum(line.split()[3] == "79" for line in source)
    print(f"{directory} MAME stage log")
    print("  First core (start, zero HP, elapsed):", first_core)
    print("  Rose core  (start, zero HP, elapsed):", rose_core)
    if rose_core[1] is not None:
        with (directory / "bullets.txt").open() as source:
            type14 = sum(kind == "14" and rose_core[0] <= int(frame) < rose_core[1]
                         for frame, _, kind, *_ in map(str.split, source))
        print(f"  Type-79 activations={roses} | Rose-phase type-14 activations={type14}")


def report_save(path):
    ram = load_ee(path)
    magic, mode, attempts, shots, misses = struct.unpack_from("<5I", ram, 0x01F5E000)
    if magic != 0x31534F52 or mode not in range(4):
        raise ValueError(f"{path}: Stage 6 barrage probe control block missing")
    records, overwritten, rolling = read_ps2_log(ram, "core")
    if not rolling or overwritten:
        raise ValueError(f"{path}: incomplete or unsupported core log")
    roses, first, last = struct.unpack_from("<3I", ram, 0x01F5C000 + 12 * 79)
    # The counts block retains 64 bins of 500 ticks, with one u16 count per projectile type.
    type14 = sum(struct.unpack_from("<H", ram, 0x01F5D000 + 2 * (16 * b + 14))[0]
                 for b in range(64))
    print(f"{path.name} mode={mode} rose_attempts={attempts} emitter_calls={shots} palette_misses={misses}")
    print("  First core (start, zero HP, elapsed):", core_timing(records, 0))
    rose_core = core_timing(records, 2)
    print("  Rose core  (start, zero HP, elapsed):", rose_core)
    print(f"  Type-79 activations={roses} first={first} last={last} | Stage type-14 activations={type14}")
    bullets, lost, _ = read_ps2_log(ram, "bullets")
    if rose_core[1] is not None and (not lost or bullets[0][-1] <= rose_core[0]):
        phase_type14 = sum(row[1] == 14 and rose_core[0] <= row[-1] < rose_core[1] for row in bullets)
        print("  Rose-phase type-14 activations:", phase_type14)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mame-trace", type=Path)
    parser.add_argument("--mame-run", type=Path)
    parser.add_argument("saves", type=Path, nargs="*")
    args = parser.parse_args()
    if not (args.mame_trace or args.mame_run or args.saves):
        parser.error("supply a MAME trace, MAME stage log directory, or PCSX2 state")
    if args.mame_trace:
        trace(args.mame_trace)
    if args.mame_run:
        report_mame_run(args.mame_run)
    for path in args.saves:
        report_save(path)


if __name__ == "__main__":
    main()
