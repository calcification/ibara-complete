#!/usr/bin/env python3
"""Print the K58 follow-up timing and rose-contact summaries."""
import argparse
import json
from math import sqrt
from pathlib import Path
from statistics import mean, stdev

ARCADE_COUNT = 17
ARCADE_MEAN = 4053
ARCADE_SD = 438
EARLIER_PS2_COUNT = 5
EARLIER_PS2_MEAN = 3663


def arcade_bursts(directory):
    with (directory / "core.txt").open() as log:
        core = [(int(fields[0]), int(fields[2])) for fields in map(str.split, log)
                if fields and fields[0] != "S" and int(fields[3], 16) == 2]
    start = next((tick for tick, hp in core if hp > 0), None)
    if start is None:
        raise ValueError(f"{directory}: rose core never had positive HP")
    stop = next((tick for tick, hp in core if tick > start and hp == 0), None)
    if stop is None:
        raise ValueError(f"{directory}: rose core never reached zero HP")
    with (directory / "roses.txt").open() as log:
        rows = [tuple(map(int, fields)) for fields in map(str.split, log) if fields]
    phase = [row for row in rows if start - 3 <= row[0] <= stop]
    main = [row for row in phase if row[3] == 0]
    if not main:
        raise ValueError(f"{directory}: incomplete rose spawn log")
    frames = len({row[0] for row in main})
    return stop - start, len(main), len(phase), frames


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trial_directory", type=Path)
    parser.add_argument("--arcade-run", action="append", type=Path, default=[],
                        help="optional completed MAME stage log with ROSES=1")
    args = parser.parse_args()
    trials = sorted((json.loads(path.read_text()) for path in args.trial_directory.glob("*.json")),
                    key=lambda row: row["seed"])
    if [row["seed"] for row in trials] != list(range(5, 15)):
        parser.error("expected exactly one complete trial for each seed 5–14")

    print("| Seed | First core | Rose core | Rose activations | Constructor frames | Rose contacts | Core contacts | HP gaps >12 |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|")
    fields = ("seed", "first_core", "rose_core", "roses", "burst_frames", "rose_contacts", "core_contacts", "long_gaps")
    for row in trials:
        print("| " + " | ".join(str(row[field]) for field in fields) + " |")
    values = [row["rose_core"] for row in trials]
    count = len(trials)
    print(f"\nNew PS2 cohort: {count}, mean {mean(values):.1f}, SD {stdev(values):.1f}, "
          f"range {min(values)}–{max(values)}.")
    combined = (sum(values) + EARLIER_PS2_COUNT * EARLIER_PS2_MEAN) / (count + EARLIER_PS2_COUNT)
    difference = mean(values) - ARCADE_MEAN
    se = sqrt(stdev(values) ** 2 / count + ARCADE_SD ** 2 / ARCADE_COUNT)
    print(f"New PS2 minus earlier arcade mean: {difference:+.1f} ({difference / ARCADE_MEAN:+.1%}), "
          f"descriptive standard error {se:.1f}.")
    print(f"Expanded PS2 mean (includes rounded historical mean): ~{combined:.1f} "
          f"({(combined / ARCADE_MEAN - 1):+.1%} vs arcade).")
    print(f"Constructor attempts per active frame: "
          f"{mean(row['rose_attempts'] / row['burst_frames'] for row in trials):.2f}.")
    print(f"Rose contacts per sampled activation: "
          f"{mean(row['rose_contacts'] / row['roses'] for row in trials):.2f}.")
    print(f"Constructor-active frames per 1,000 rose-core ticks: "
          f"{mean(1000 * row['burst_frames'] / row['rose_core'] for row in trials):.2f}.")
    for directory in args.arcade_run:
        elapsed, primary, all_roses, frames = arcade_bursts(directory)
        print(f"{directory.name}: {elapsed} rose-core frames, {primary}/{all_roses} primary/all rose "
              f"activations, {frames} distinct primary spawn frames "
              f"({1000 * frames / elapsed:.2f} per 1,000 rose-core frames).")


if __name__ == "__main__":
    main()
