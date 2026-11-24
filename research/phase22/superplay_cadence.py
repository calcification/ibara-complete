#!/usr/bin/env python3
"""Export confirmed arcade footage repeats as a PS2 cadence test window."""

import argparse
import csv
from pathlib import Path

from audit_superplay import crop_argument, decode_fields, field_deltas, repeat_runs


def consensus_ticks(source, crops, anchor, refreshes):
    end = anchor + refreshes
    detected = []
    for crop in crops:
        fields, pts = decode_fields(source, crop)
        if anchor < 24 or end >= len(pts) - 24:
            raise ValueError("keep the whole timing window within the trimmed footage")
        runs = repeat_runs(pts, field_deltas(fields), trim=24, ratio=.45, min_pairs=8)
        detected.append({
            field for run in runs for field in range(run["first_field"] + 1, run["last_field"] + 1, 2)
        })
    common = set.intersection(*detected)
    ticks = [0]
    for field in range(anchor + 1, end + 1):
        ticks.append(ticks[-1] + (field not in common))
    if ticks[-1] == ticks[-2]:
        raise ValueError("the last observation is a hold. End the window on an advancing field")
    return ticks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mpeg_segment", type=Path)
    parser.add_argument("--crop", action="append", type=crop_argument, required=True, metavar="W:H:X:Y")
    parser.add_argument("--anchor-field", type=int, required=True)
    parser.add_argument("--refreshes", type=int, required=True)
    parser.add_argument("--window", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if len(set(args.crop)) < 2 or args.refreshes < 1 or not args.window.strip():
        parser.error("use at least two distinct crops, a positive refresh count, and a window name")
    try:
        ticks = consensus_ticks(args.mpeg_segment, args.crop, args.anchor_field, args.refreshes)
        with args.output.open("x", newline="", encoding="utf-8") as output:
            writer = csv.writer(output)
            writer.writerow(("window", "frame", "tick"))
            writer.writerows((args.window, frame, tick) for frame, tick in enumerate(ticks))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"{args.window}: {args.refreshes - ticks[-1]} holds in {args.refreshes} refreshes")


if __name__ == "__main__":
    main()
