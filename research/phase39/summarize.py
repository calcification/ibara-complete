#!/usr/bin/env python3
"""Summarize directional and target-transition traces from Stage 2 homing pods."""
import argparse
import csv
from pathlib import Path

CENTER = {0: 0, 1: 256, 2: 0, 4: 128, 5: 192, 6: 64, 8: 384, 9: 320, 10: 448}


def capture(path):
    with path.open() as stream:
        rows = [{key: int(value) for key, value in row.items()} for row in csv.DictReader(stream)]
    if [(row["tick"], row["pod"]) for row in rows] != [(tick, pod) for tick in range(800) for pod in range(3)]:
        raise ValueError(f"{path}: expected 800 consecutive three-pod samples")
    return rows


def headings(rows, mask):
    tick = next(i for i in range(10, 190, 20) if rows[3 * i]["mask"] == mask)
    return "/".join(str(rows[3 * tick + pod]["desired"]) for pod in range(3))


def stats(rows):
    misses = matched = gains = losses = 0
    for index, row in enumerate(rows):
        valid = row["target"] < 192
        if not valid:
            misses += 1
            expected = (288, 224, CENTER[row["mask"]])[row["pod"]]
            matched += row["desired"] == expected
        if index >= 3:
            previously_valid = rows[index - 3]["target"] < 192
            gains += valid and not previously_valid
            losses += previously_valid and not valid
    return misses, matched, gains, losses


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    names = ("bl-empty", "bl-live", "ps2-stock-empty", "ps2-stock-live",
             "ps2-formation-empty", "ps2-formation-live")
    traces = {name: capture(args.directory / f"{name}.csv") for name in names}
    print("| Input | MAME empty | PS2 stock empty | PS2 formation empty |")
    print("|---|---|---|---|")
    for mask, label in zip((0, 1, 5, 4, 6, 2, 10, 8, 9),
                           ("None", "Up", "Up-left", "Left", "Down-left",
                            "Down", "Down-right", "Right", "Up-right")):
        print(f"| {label} | " + " | ".join(headings(traces[name], mask) for name in names[::2]) + " |")
    print()
    print("| Trace | No-target samples | Formation-heading matches | Acquisitions | Losses |")
    print("|---|---:|---:|---:|---:|")
    for name, rows in traces.items():
        print(f"| {name} | " + " | ".join(map(str, stats(rows))) + " |")


if __name__ == "__main__":
    main()
