#!/usr/bin/env python3
"""Summarize repeat Stage 1–5 damage captures without counting escapes as kills."""
import argparse
from collections import defaultdict
import csv
from pathlib import Path
from statistics import mean, stdev


def trial(path):
    rows = []
    stage = seed = None
    with path.open() as capture:
        for line in capture:
            fields = line.split()
            if not fields:
                continue
            if fields[0] == "#":
                if fields[1:2] == ["stage"]:
                    stage, seed = int(fields[2]), int(fields[4])
                continue
            tick, slot, hp = map(int, fields[:3])
            if int(fields[3], 16) == 0:
                rows.append((tick, slot, hp))
    if stage is None or seed is None:
        raise ValueError(f"{path}: stage and seed header missing")
    if not rows or not any(hp > 0 for _, _, hp in rows):
        return stage, seed, "no positive HP", None, None
    if len({slot for _, slot, _ in rows}) != 1:
        return stage, seed, "ambiguous core", None, None
    if any(b[0] <= a[0] for a, b in zip(rows, rows[1:])):
        raise ValueError(f"{path}: samples must be chronological within one core")
    start, _, initial = next(row for row in rows if row[2] > 0)
    zero = next((tick for tick, _, hp in rows if tick > start and hp == 0), None)
    status = "kill" if zero is not None else "zero HP unobserved"
    return stage, seed, status, initial, (zero - start if zero is not None else rows[-1][0] - start)


def collect(root, system):
    for file in sorted(root.glob("stage*/*.txt")):
        stage, seed, status, hp, elapsed = trial(file)
        if file.parent.name != f"stage{stage}" or file.stem != str(seed):
            raise ValueError(f"{file}: path does not match its stage and seed header")
        yield stage, system, seed, status, hp, elapsed


def describe(trials):
    values = [elapsed for _, status, elapsed in trials if status == "kill"]
    if not values:
        return "0/" + str(len(trials)), "—", "—", "—", values
    spread = f"{stdev(values):.1f}" if len(values) > 1 else "—"
    return f"{len(values)}/{len(trials)}", f"{mean(values):.1f}", spread, f"{min(values)}–{max(values)}", values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bl", type=Path, required=True)
    parser.add_argument("--ps2", type=Path, required=True)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--min-seeds", type=int, default=8)
    args = parser.parse_args()
    if args.min_seeds < 1:
        parser.error("--min-seeds must be positive")
    stages = defaultdict(list)
    trials = sorted([*collect(args.bl, "BL"), *collect(args.ps2, "Noir")])
    for stage, system, seed, status, _, elapsed in trials:
        stages[stage, system].append((seed, status, elapsed))
    if args.csv:
        with args.csv.open("w", newline="") as output:
            writer = csv.writer(output)
            writer.writerow(("stage", "system", "seed", "status", "initial_hp", "elapsed_or_observed"))
            writer.writerows(trials)

    print("| Stage | BL kills / trials | BL mean | BL SD | BL range | Noir kills / trials | Noir mean | Noir SD | Noir range | Noir vs BL range |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for stage in range(1, 6):
        bl = stages[stage, "BL"]
        ps2 = stages[stage, "Noir"]
        *left, bl_kills = describe(bl)
        *right, ps2_kills = describe(ps2)
        comparison = "Awaiting seed coverage"
        if min(len(bl), len(ps2)) >= args.min_seeds:
            comparison = "Insufficient observed kills"
            if min(len(bl_kills), len(ps2_kills)) >= args.min_seeds:
                below = sum(v < min(bl_kills) for v in ps2_kills)
                above = sum(v > max(bl_kills) for v in ps2_kills)
                comparison = f"{below} below, {above} above"
        print("| " + " | ".join(map(str, (stage, *left, *right, comparison))) + " |")


if __name__ == "__main__":
    main()
