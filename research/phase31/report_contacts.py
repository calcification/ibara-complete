#!/usr/bin/env python3
"""Summarize native Stage 6 projectile contacts and damage in both emulators."""
import argparse
from collections import Counter
from pathlib import Path
from statistics import median
import struct
import sys
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(ROOT / "scripts"), str(ROOT / "tools/stage_compare"), str(ROOT / "research/phase30"),
]
from run_stage import read_ps2_log
from p2s_tools import load_ee
from report_roses import core_timing

PS2_HEADER = 0x01F90000
CORE_SUBTYPES = (0, 2)


class Event(NamedTuple):
    tick: int
    kind: int
    subtype: int
    shot_type: int
    flash: int
    hp_loss: int
    before_hp: int


def read_mame(directory):
    cores, events = [], []
    with (directory / "core.txt").open() as log:
        for row in log:
            tick, slot, hp, subtype, *_ = row.split()
            cores.append((0, int(slot), int(hp), int(subtype, 16), 7, int(tick)))
    with (directory / "contacts.txt").open() as log:
        for row in log:
            tag, tick, _, kind, subtype, before, value, _, shot_type = row.split()
            flash = int(value) if tag == "C" else -1
            loss = int(before) - int(value) if tag == "H" else 0
            events.append(Event(int(tick), int(kind), int(subtype), int(shot_type), flash, loss, int(before)))
    return cores, events


def read_ps2(path):
    ram = load_ee(path)
    magic, count, dropped, pending = struct.unpack_from("<4I", ram, PS2_HEADER)
    if magic != 0x31544948 or not 0 < count <= 24000 or dropped or pending:
        raise ValueError(f"{path}: incomplete trace (count {count}, dropped {dropped}, pending {pending:#x})")
    cores, lost, rolling = read_ps2_log(ram, "core")
    if not rolling or lost:
        raise ValueError(f"{path}: incomplete core log")
    record = struct.Struct("<IBBBBHH4x")
    events = []
    for i in range(count):
        address = PS2_HEADER + 32 + i * record.size
        tick, kind, subtype, flash, shot, before, after = record.unpack_from(ram, address)
        events.append(Event(tick, kind, subtype, shot, flash, max(0, before - after), before))
    return cores, events


def summarize(label, cores, events):
    print(f"\n{label}")
    print("Target            Elapsed   Calls  Flash active   HP lost   Median HP-step gap")
    for subtype in CORE_SUBTYPES:
        start, stop, elapsed = core_timing(cores, subtype)
        if stop is None:
            raise ValueError(f"{label}: core subtype {subtype} did not reach zero")
        window = [e for e in events if start - 3 <= e.tick <= stop]
        for kind in ((74, 79) if subtype == 2 else (74,)):
            selected = [e for e in window if e.kind == kind and (kind == 79 or e.subtype == subtype)]
            contacts = [e for e in selected if e.flash >= 0]
            hits = [e for e in selected if e.hp_loss]
            gaps = [b.tick - a.tick for a, b in zip(hits, hits[1:])]
            lost = sum(e.hp_loss for e in hits)
            name = f"core subtype {subtype}" if kind == 74 else "rose interceptions"
            print(f"{name:18} {elapsed:7} {len(contacts):7} {sum(e.flash > 0 for e in contacts):13} "
                  f"{lost:9} {median(gaps) if gaps else '-':>20}")
            print(f"  Contacts by shot type: {dict(sorted(Counter(e.shot_type for e in contacts).items()))}")
            print(f"  HP steps by shot type: {dict(sorted(Counter(e.shot_type for e in hits).items()))}")
            if kind == 74:
                sampled_hp = next(row[2] for row in cores if row[3] == subtype and row[-1] == start)
                initial_hp = max([sampled_hp, *(e.before_hp for e in selected if e.tick <= start)])
                if lost != initial_hp or sampled_hp != initial_hp:
                    print(f"  Coverage: {lost}/{initial_hp} HP traced, first sample {sampled_hp}")
                if hits:
                    print(f"  First HP step: tick {hits[0].tick} (sample starts at {start})")


def report_mame_core_writers(log, cores):
    """Count core HP stores whether or not they came from an ordinary shot."""
    windows = {subtype: core_timing(cores, subtype)[:2] for subtype in CORE_SUBTYPES}
    writers = {subtype: Counter() for subtype in windows}
    initial_hp = {}
    for row in log:
        tick, _, subtype, before, after, pc, caller = row.split()
        tick, subtype, before, after = map(int, (tick, subtype, before, after))
        start, stop = windows[subtype]
        if stop is not None and start - 3 <= tick <= stop and before > after:
            writers[subtype][pc, caller] += before - after
            initial_hp.setdefault(subtype, before)
    print("MAME direct core stores, including other damage paths")
    for subtype, counts in writers.items():
        print(f"  Core {subtype}: {sum(counts.values())}/{initial_hp.get(subtype, 0)} HP traced")
        for (pc, caller), hp in counts.most_common():
            print(f"    {hp:3} HP at {pc}, return PC {caller}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mame-run", type=Path)
    parser.add_argument("saves", type=Path, nargs="*")
    args = parser.parse_args()
    if not (args.mame_run or args.saves):
        parser.error("provide a MAME run directory or a PCSX2 state")
    if args.mame_run:
        cores, events = read_mame(args.mame_run)
        summarize(args.mame_run, cores, events)
        core_writes = args.mame_run / "core-writes.txt"
        if core_writes.exists():
            with core_writes.open() as log:
                report_mame_core_writers(log, cores)
    for path in args.saves:
        summarize(path.name, *read_ps2(path))


if __name__ == "__main__":
    main()
