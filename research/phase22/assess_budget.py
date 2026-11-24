#!/usr/bin/env python3
"""Fit an integer workload budget to MAME holds and test it on unseen Arcade routes."""

import argparse
from collections import deque
import csv
import gzip
import json
from pathlib import Path

from assess_workload import COUNTS, HISTORY, prepare_route
from score_slowdown import compare, slowdowns


ONE = 4096
SCALES = (256, 192, 96, 256)


def workload(counts):
    previous = counts[0]
    recent = deque(maxlen=HISTORY)
    for current in counts:
        levels = [v * ONE // size for v, size in zip(current, SCALES)]
        churn = [abs(a - b) * ONE // size for a, b, size in zip(current, previous, SCALES)]
        bullets, enemies, _, _ = levels
        # Take one product as a proxy for interactions between object pools.
        recent.append((ONE, *levels, bullets * enemies // ONE, *churn))
        yield tuple(sum(column) // len(recent) for column in zip(*recent))
        previous = current


def predict(rows, weights):
    # Units are fractions of one extra refresh. Reset on a quiet update and
    # cap each update's contribution so two holds cannot occur back-to-back.
    ticks, debt = [0], 0
    for tick, row in enumerate(rows):
        load = sum(weight * value for weight, value in zip(weights, row)) // ONE
        debt = debt + min(load, ONE) if load > 0 else 0
        if debt >= ONE:
            ticks.append(tick)
            debt -= ONE
        ticks.append(tick + 1)
    return ticks


def fit(routes):
    features, targets = [], []
    for route in routes:
        features.extend(workload(route.counts))
        held = {a - route.ticks[0] for a, b in zip(route.ticks, route.ticks[1:]) if a == b}
        for tick in range(len(route.counts)):
            recent = range(max(0, tick - HISTORY + 1), tick + 1)
            targets.append(sum(t in held for t in recent) / len(recent))

    columns = [tuple(v / ONE for v in col) for col in zip(*features)]
    coefficients = [0.0] * len(columns)
    errors = targets.copy()
    norms = [sum(v * v for v in col) + 1.0 for col in columns]
    for _ in range(120):
        for i, column in enumerate(columns):
            before = coefficients[i]
            adjustment = sum(v * error for v, error in zip(column, errors)) / norms[i]
            updated = before + adjustment
            coefficients[i] = max(0.0, updated) if i else min(0.0, updated)
            delta = coefficients[i] - before
            errors = [error - delta * v for v, error in zip(column, errors)]

    reference = {route.name: route.ticks for route in routes}
    route_features = {route.name: list(workload(route.counts)) for route in routes}
    best = None
    for gain in (0.5, 1.0, 1.5, 2.0, 3.0):
        for offset in (-0.25, -0.125, -0.0625, 0.0, 0.0625, 0.125):
            weights = [round(v * gain * ONE) for v in coefficients]
            weights[0] = min(0, weights[0] + round(offset * ONE))
            candidate = {name: predict(rows, weights) for name, rows in route_features.items()}
            report = compare(reference, candidate, "diagnostic")
            hold_error = sum(abs(len(ticks) - len(candidate[name])) for name, ticks in reference.items())
            objective = (report["score_percent"] or 0, -report["extra_events"], -hold_error)
            if best is None or objective > best[0]:
                best = objective, weights
    return best[1]


def score(routes, weights):
    reference = {route.name: route.ticks for route in routes}
    candidate = {route.name: predict(workload(route.counts), weights) for route in routes}
    return compare(reference, candidate, "diagnostic")


def read_quiet(path, columns=COUNTS):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", newline="", encoding="utf-8") as source:
        rows = [tuple(int(row[key]) for key in ("gameplay_tick", "holding", "scene", *columns))
                for row in csv.DictReader(source)]
    if not rows or any(row[1:3] != (0, 2) for row in rows) or any(
        b[0] != a[0] + 1 for a, b in zip(rows, rows[1:])
    ):
        raise ValueError(f"{path}: expected a continuous stock Stage 1 capture")
    return [row[3:] for row in rows]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", nargs=3, required=True, metavar=("NAME", "MAME", "STOCK"))
    parser.add_argument("--quiet", type=Path, required=True, help="stock Stage 1 workload CSV")
    args = parser.parse_args()
    if len(args.case) < 2 or len({case[0] for case in args.case}) != len(args.case):
        parser.error("supply at least two distinct named cases")
    try:
        routes = [prepare_route(name, Path(mame), Path(stock)) for name, mame, stock in args.case]
        quiet = list(workload(read_quiet(args.quiet)))
        folds = []
        for holdout in routes:
            training = [route for route in routes if route is not holdout]
            weights = fit(training)
            quiet_trace = predict(quiet, weights)
            folds.append({"weights_q12": weights, "training": score(training, weights),
                          "held_out": score([holdout], weights), "stage1_events": len(slowdowns(quiet_trace)),
                          "stage1_holds": len(quiet_trace) - len(quiet) - 1})
    except (KeyError, OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(folds, indent=2))


if __name__ == "__main__":
    main()
