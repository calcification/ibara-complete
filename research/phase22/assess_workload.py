#!/usr/bin/env python3
"""Fit single-signal slowdown thresholds and score them on a different route."""

import argparse
from collections import Counter
import csv
from dataclasses import dataclass
import gzip
import json
from pathlib import Path

from score_slowdown import compare, matching_pairs, read_trace, slowdowns


COUNTS = ("hostile_bullets", "active_enemies", "rose_pods", "active_items")
HISTORY = 8


@dataclass
class Route:
    name: str
    ticks: list[int]
    counts: list[tuple[int, ...]]
    signals: dict[str, list[int]]


def stock_counts(path, duration, columns=COUNTS):
    opener = gzip.open if path.suffix == ".gz" else open
    fields = ("outer_loop", "gameplay_tick", "released_buttons", "holding", "scene", *columns)
    with opener(path, "rt", newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        if not set(fields) <= set(reader.fieldnames or []):
            raise ValueError(f"{path}: expected a stock S01 workload capture")
        rows = [tuple(int(row[key]) for key in fields) for row in reader]
    release = next((i for i, row in enumerate(rows) if row[2] & 0x20), -1)
    if release < 2 * HISTORY or release + 1 + duration >= len(rows):
        raise ValueError(f"{path}: need the bomb release, its lead-in, and the full window")
    window = rows[release + 1 - 2 * HISTORY:release + 2 + duration]
    if any(row[3] or row[4] != 7 for row in window) or any(
        b[0] != a[0] + 1 or b[1] != a[1] + 1 for a, b in zip(window, window[1:])
    ):
        raise ValueError(f"{path}: expected continuous full-speed Stage 6 samples")
    return [row[5:] for row in window[:-1]]


def prepare_route(name, reference, stock):
    ticks = read_trace(reference)[name]
    counts = stock_counts(stock, ticks[-1] - ticks[0])
    series = dict(zip(COUNTS, zip(*counts)))
    # Rose Pods are already included in the active enemy count.
    series["total_objects"] = [bullets + enemies + items for bullets, enemies, _, items in counts]
    signals = {}
    for label, values in series.items():
        signals[label] = list(values[2 * HISTORY:])
        recent = [sum(values[i - HISTORY + 1:i + 1]) for i in range(HISTORY - 1, len(values))]
        signals[f"{label}_sum8"] = recent[HISTORY + 1:]
        signals[f"{label}_change8"] = [
            current - older for older, current in zip(recent[1:], recent[HISTORY + 1:])
        ]
    return Route(name, ticks, counts[2 * HISTORY:], signals)


def predict(values, threshold):
    ticks = [0]
    for tick, value in enumerate(values):
        if value >= threshold:
            ticks.append(tick)
        ticks.append(tick + 1)
    return ticks


def fit(routes):
    reference = [slowdowns(route.ticks) for route in routes]
    labels = [{a for a, b in zip(route.ticks, route.ticks[1:]) if a == b} for route in routes]
    best = None
    for signal in routes[0].signals:
        levels = {v for route in routes for v in route.signals[signal]}
        for threshold in sorted(levels | {max(levels) + 1}):
            matches = misses = extras = disagreement = 0
            for route, expected, expected_ticks in zip(routes, reference, labels):
                candidate = slowdowns(predict(route.signals[signal], threshold))
                matched = len(matching_pairs(expected, candidate))
                matches += matched
                misses += len(expected) - matched
                extras += len(candidate) - matched
                holds = {route.ticks[0] + i for i, v in enumerate(route.signals[signal]) if v >= threshold}
                disagreement += len(holds ^ expected_ticks)
            total = matches + misses + extras
            score = matches / total if total else 1.0
            objective = (score, matches, -extras, -disagreement)
            if best is None or objective > best[0]:
                best = objective, signal, threshold
    _, signal, threshold = best
    return signal, threshold


def report(routes, rule):
    signal, threshold = rule
    reference = {route.name: route.ticks for route in routes}
    candidate = {route.name: predict(route.signals[signal], threshold) for route in routes}
    return {"signal": signal, "threshold": threshold, **compare(reference, candidate, "diagnostic")}


def count_ambiguity(routes):
    occurrences = {}
    for route in routes:
        held = {a - route.ticks[0] for a, b in zip(route.ticks, route.ticks[1:]) if a == b}
        for tick, state in enumerate(route.counts):
            occurrences.setdefault(state, Counter())[tick in held] += 1
    return sum(min(count.values()) for count in occurrences.values() if len(count) == 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", nargs=3, required=True, metavar=("NAME", "REFERENCE", "STOCK"))
    args = parser.parse_args()
    if len(args.case) < 2 or len({case[0] for case in args.case}) != len(args.case):
        parser.error("supply at least two distinct named cases")
    try:
        routes = [prepare_route(name, Path(ref), Path(stock)) for name, ref, stock in args.case]
        folds = []
        for holdout in routes:
            training = [route for route in routes if route is not holdout]
            rule = fit(training)
            folds.append({"training": report(training, rule), "held_out": report([holdout], rule)})
        result = {
            "folds": folds,
            "fit_on_all_cases": report(routes, fit(routes)),
            "minimum_wrong_tick_labels_from_counts_alone": count_ambiguity(routes),
            "total_gameplay_ticks": sum(len(route.counts) for route in routes),
        }
    except (KeyError, OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
