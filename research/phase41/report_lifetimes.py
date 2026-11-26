#!/usr/bin/env python3
"""Compare complete Stage 2 pod slot lifetimes and target changes."""
import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean, median
import struct

ROW = struct.Struct("<48B9H")
EVENT = struct.Struct("<HBB")
KINDS = {3: 5, 6: 3}
FORMATION = (288, 224, 0)


def completed_lifetimes(events):
    births, durations, launched = {}, [], 0
    for frame, slot, allocated in events:
        if allocated:
            if slot in births:
                raise ValueError(f"slot {slot} reused before its release at update {frame}")
            births[slot] = frame
            launched += 1
        elif slot in births:
            durations.append(frame - births.pop(slot))
    return durations, launched


def snapshot_events(rows, kind):
    """Birth only when a shot first appears, free when the slot next reads zero."""
    previous = rows[0][:48]
    for frame, row in enumerate(rows[1:], 1):
        for slot, code in enumerate(row[:48]):
            if code == kind and previous[slot] != kind:
                yield frame, slot, 1
            if code == 0 and previous[slot] != 0:
                yield frame, slot, 0
        previous = row[:48]


def trace(directory, weapon, seed):
    base = directory / f"{weapon}-{seed}"
    rows = list(ROW.iter_unpack(base.with_suffix(".trace").read_bytes()))
    if len(rows) != 1000:
        raise ValueError(f"{base}: expected 1,000 trace rows")
    projectile = KINDS[weapon]
    exact = base.with_suffix(".trace.events")
    if exact.exists():
        fields = list(map(int, base.with_suffix(".txt").read_text().splitlines()[0].split()))
        allocations, occupied = fields[3], fields[5]
        durations, observed = completed_lifetimes(EVENT.iter_unpack(exact.read_bytes()))
        if observed != allocations:
            raise ValueError(f"{base}: exact event count disagrees with the census")
    else:
        result = json.loads(base.with_suffix(".json").read_text())
        allocations, occupied = result["allocations"], result["occupied"]
        durations, observed = completed_lifetimes(snapshot_events(rows, projectile))
        if result["sampled"] != allocations or not 0 <= allocations - observed <= 48:
            raise ValueError(f"{base}: snapshot births missed an allocation")
    shot_frames = sum(row[:48].count(projectile) for row in rows)
    if shot_frames != occupied:
        raise ValueError(f"{base}: trace occupancy disagrees with the census")
    slot_frames = sum(48 - row[:48].count(0) for row in rows)
    other = Counter(code - 1 for row in rows for code in row[:48] if code not in (0, projectile))
    valid = formation_on_valid = acquisitions = losses = eased_losses = 0
    if weapon == 3:
        for frame, row in enumerate(rows):
            for pod, formation in enumerate(FORMATION):
                target, desired, heading = (row[48 + pod], row[51 + pod], row[54 + pod])
                has_target = target < 192
                valid += has_target
                formation_on_valid += has_target and desired == formation
                if frame:
                    previously_targeted = rows[frame - 1][48 + pod] < 192
                    acquisitions += has_target and not previously_targeted
                    if previously_targeted and not has_target:
                        losses += 1
                        eased_losses += desired == formation and heading != desired
    return allocations, shot_frames, slot_frames, durations, other, (
        valid, formation_on_valid, acquisitions, losses, eased_losses)


def mean_string(values):
    return f"{mean(values):.2f}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", type=Path, action="append", required=True, help="trace directory")
    args = parser.parse_args()
    print("| Cohort | Weapon | Launches | Projectile slots | Other occupied slots | Complete lifetimes | Mean / median updates |")
    print("|---|---|---:|---:|---:|---:|---:|")
    target_reports, other_reports = [], []
    for directory in args.cohort:
        for weapon in (3, 6):
            counts = [trace(directory, weapon, seed) for seed in (1, 2, 3)]
            launches, shot, slots, life, other, targets = zip(*counts)
            lifetimes = [age for ages in life for age in ages]
            other_types = sum(other, Counter())
            print(f"| {directory.name} | {weapon} | {mean_string(launches)} | {mean(shot)/1000:.2f} | "
                  f"{(mean(slots)-mean(shot))/1000:.2f} | {len(lifetimes)} | "
                  f"{mean_string(lifetimes)} / {median(lifetimes):g} |")
            if other_types:
                other_reports.append((directory.name, weapon, dict(other_types.most_common(6))))
            if weapon == 3:
                target_reports.append((directory.name, *map(sum, zip(*targets))))
    print("\n| Cohort | Valid target samples | Formation angle with valid target | Acquisitions | Losses | Eased losses |")
    print("|---|---:|---:|---:|---:|---:|")
    for row in target_reports:
        print("| " + " | ".join(map(str, row)) + " |")

    print("\n| Cohort | Weapon | Other slot occupancy by native kind |")
    print("|---|---:|---|")
    for row in other_reports:
        print("| " + " | ".join(map(str, row)) + " |")


if __name__ == "__main__":
    main()
