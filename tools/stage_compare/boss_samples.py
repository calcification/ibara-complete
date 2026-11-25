#!/usr/bin/env python3
"""Summarize repeat boss captures by stage and core subtype.

Each trial directory must contain bl_core.txt and ps2_core.txt from run_stage.py.
Use one or more separate trials from the same stage and the same input protocol.
A sampled HP of zero is evidence of depleting the core. Disappearance with HP
remaining can also be a timeout, an escape, or the end of the recording.
"""
import argparse
import statistics
from pathlib import Path


def read_core(path, subtype):
    matches = []
    with path.open() as source:
        for line in source:
            frame, slot, hp, kind, *_ = line.split()
            if int(kind, 16) == subtype:
                matches.append((int(frame), int(slot), int(hp)))
    if not matches:
        raise ValueError(f"{path}: no core of subtype {subtype:#x}")
    if len({slot for _, slot, _ in matches}) != 1:
        raise ValueError(f"{path}: multiple slots for subtype {subtype:#x}; isolate the intended form")
    if not matches[0][2]:
        raise ValueError(f"{path}: core starts at zero HP; this subtype is unsuitable for a damage comparison")
    return matches


def summarize(samples):
    first, _, initial = samples[0]
    last, _, final = samples[-1]
    zero = next((frame - first for frame, _, hp in samples if hp == 0), None)
    return initial, final, last - first, zero


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trial", type=Path, nargs="+")
    parser.add_argument("--subtype", type=lambda value: int(value, 0), default=0)
    args = parser.parse_args()
    observed = {"bl": [], "ps2": []}
    print("Trial\tSystem\tHP first\tHP last\tObserved frames\tFrames to zero HP")
    for trial in args.trial:
        for system in observed:
            try:
                initial, final, span, zero = summarize(read_core(trial / f"{system}_core.txt", args.subtype))
            except ValueError as error:
                parser.error(str(error))
            if zero is not None:
                observed[system].append(zero)
            print(f"{trial}\t{system}\t{initial}\t{final}\t{span}\t{zero if zero is not None else 'unobserved'}")
    for system, values in observed.items():
        if values:
            print(f"{system}: zero HP in {len(values)}/{len(args.trial)} trials, median {statistics.median(values):g}"
                  f" frames, range {min(values)}–{max(values)}")
        else:
            print(f"{system}: zero HP unobserved in all {len(args.trial)} trials")


if __name__ == "__main__":
    main()
