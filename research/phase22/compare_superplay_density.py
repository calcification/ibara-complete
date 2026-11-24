#!/usr/bin/env python3
"""Fit a screen-density threshold on one DVD run and test on another.

This diagnostic works on visible alternate-field repeats. It does not score
PS2 gameplay, recover variable-rate holds, or set any patch parameters.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from audit_superplay import decode_fields, field_deltas, repeat_runs
from score_slowdown import matching_pairs, slowdowns


CROP = (332, 360, 54, 66)
TRIM = 24


def measure(path):
    fields, pts = decode_fields(path, CROP)
    runs = repeat_runs(pts, field_deltas(fields), TRIM, .45, 8)
    dense = (fields[:, 8:80, 4:-4] >= 120).mean(axis=(1, 2))
    repeating = np.zeros(len(fields), dtype=bool)
    for run in runs:
        repeating[run["first_field"]:run["last_field"] + 1] = True
    return dense[TRIM:-TRIM], repeating[TRIM:-TRIM]


def counts(predicted, expected):
    return (
        int(np.count_nonzero(predicted & expected)),
        int(np.count_nonzero(predicted & ~expected)),
        int(np.count_nonzero(~predicted & expected)),
    )


def f1(correct, extra, missed):
    denominator = 2 * correct + extra + missed
    return (2 * correct) / denominator if denominator else 0.0


def timing_events(repeating):
    # A field pair represents one advancing and one held field. Keep this
    # inferred cadence local to the DVD diagnostic.
    edges = np.flatnonzero(np.diff(repeating, prepend=False, append=False))
    held = np.zeros(len(repeating), dtype=bool)
    for first, end in zip(edges[::2], edges[1::2]):
        held[first + 1:end:2] = True
    return slowdowns(np.cumsum(~held).tolist())


def compare(predicted, expected):
    reference_events = timing_events(expected)
    predicted_events = timing_events(predicted)
    matches = len(matching_pairs(reference_events, predicted_events))
    return matches, len(predicted_events) - matches, len(reference_events) - matches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", required=True, nargs="+", type=Path)
    parser.add_argument("--validate", required=True, nargs="+", type=Path)
    args = parser.parse_args()
    if {path.resolve() for path in args.train} & {path.resolve() for path in args.validate}:
        parser.error("use separate clips for training and validation")
    try:
        train_density, train_expected = map(np.concatenate, zip(*(measure(path) for path in args.train)))
        validation = [measure(path) for path in args.validate]
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if not train_expected.any() or train_expected.all() or not any(expected.any() for _, expected in validation):
        parser.error("train on both cadences and include visible repeats in validation")
    thresholds = np.quantile(train_density, np.linspace(0, 1, 201))
    best = max(thresholds, key=lambda threshold: f1(*counts(train_density >= threshold, train_expected)))
    fields = [counts(density >= best, expected) for density, expected in validation]
    events = [compare(density >= best, expected) for density, expected in validation]
    matched, extra, missed = map(sum, zip(*events))
    print(json.dumps({
        "luma_coverage_threshold": round(float(best), 5),
        "training_field_f1": round(f1(*counts(train_density >= best, train_expected)), 3),
        "validation_field_f1": round(f1(*map(sum, zip(*fields))), 3),
        "validation_events": {"matched": matched, "extra": extra, "missed": missed},
    }, indent=2))


if __name__ == "__main__":
    main()
