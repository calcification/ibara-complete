#!/usr/bin/env python3
"""Compare true pod allocations against the frame-end census."""
import argparse
import json
from pathlib import Path
from statistics import mean

WEAPONS = {6: ("5-way", 5), 3: ("Homing", 1), 4: ("Napalm", 1)}
KEYS = ("weapon", "seed", "frames", "allocations", "sampled", "occupied", "attempts", "x", "y", "ship")


def arcade(path):
    with path.open() as source:
        row = dict(zip(KEYS, map(int, source.readline().split()), strict=True))
        writes = {pc: int(count) for pc, count in map(str.split, source)}
    if len(writes) != 1 or sum(writes.values()) != row["allocations"]:
        raise ValueError(f"{path}: unexpected projectile writers {writes}")
    return row


def describe(rows, volley):
    allocations = [r["allocations"] for r in rows]
    attempts = sum(r["attempts"] for r in rows)
    launched = sum(allocations)
    if not 0 < launched <= attempts * volley or any(
        r["frames"] != 1000 or r["allocations"] % volley or r["sampled"] > r["allocations"] for r in rows
    ):
        raise ValueError("inconsistent exposure or volley totals")
    return f"{mean(allocations):.1f} ({min(allocations)}–{max(allocations)})", \
        mean(r["sampled"] for r in rows), mean(r["attempts"] for r in rows), \
        100 * launched / (attempts * volley), mean(r["occupied"] / 1000 for r in rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("arcade", type=Path)
    parser.add_argument("ps2", type=Path)
    parser.add_argument("--weapon", type=int, choices=WEAPONS, action="append")
    args = parser.parse_args()
    print("| Weapon | Engine | Allocations (range) | Sampled | Attempts | Success | Mean alive |")
    print("|---|---|---:|---:|---:|---:|---:|")
    for weapon in args.weapon or WEAPONS:
        name, volley = WEAPONS[weapon]
        bl, ps2 = [], []
        for seed in range(1, 4):
            bl.append(arcade(args.arcade / f"{weapon}-{seed}.txt"))
            ps2.append(json.loads((args.ps2 / f"{weapon}-{seed}.json").read_text()))
            if (bl[-1]["weapon"], bl[-1]["seed"]) != (weapon, seed) or \
                    (ps2[-1]["weapon"], ps2[-1]["seed"]) != (weapon, seed):
                raise ValueError(f"unmatched weapon {weapon} seed {seed}")
            if bl[-1]["ship"] or (bl[-1]["x"], bl[-1]["y"]) != (ps2[-1]["x"], ps2[-1]["y"]):
                raise ValueError(f"player position or ship differs in weapon {weapon} seed {seed}")
        for engine, rows in (("MAME", bl), ("PCSX2", ps2)):
            actual, sampled, tries, success, alive = describe(rows, volley)
            print(f"| {name} | {engine} | {actual} | {sampled:.1f} | {tries:.1f} | {success:.1f}% | {alive:.2f} |")


if __name__ == "__main__":
    main()
