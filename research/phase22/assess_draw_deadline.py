#!/usr/bin/env python3
"""Fit arcade draw-list CPU cost on one route and test it on another."""
import argparse
import csv
from dataclasses import dataclass
import gzip
from itertools import groupby, pairwise
import json
from pathlib import Path
from statistics import median

import numpy as np

from assess_workload import HISTORY, predict, stock_counts
from score_slowdown import compare
from workload_capture import CYCLE_HEADER

IRQ_PERIOD_MS = 1000 / 60.024
LIST_PUBLISHED = 0x19671010
DRAW_PHASES = ("draw_parts", "draw_setup", "draw_overlays", "publish")
SIM_PHASES = ("sim_a", "sim_b", "sim_c")
COST_FEATURES = {
    "draw_count": ("draws",),
    "command_mix": ("visible_draws", "offscreen_draws", "blended_draws", "upload_bytes"),
}


@dataclass
class Route:
    name: str
    ticks: list[int]
    updates: list[dict]


def read_route(path, name=None):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", newline="") as source:
        rows = list(csv.DictReader(source))
    if len(rows) < 2 or int(rows[0]["tick"]) != 0:
        raise ValueError(f"{path}: expected a capture starting at tick zero")
    ticks = [int(row["tick"]) for row in rows]
    window = rows[0]["window"]
    for index, (a, b) in enumerate(pairwise(rows)):
        irq_delta = (int(b["irq_outer"]) - int(a["irq_outer"])) & 0xFFFFFFFF
        if (a["window"] != window or b["window"] != window or int(a["frame"]) != index
                or int(b["frame"]) != index + 1 or ticks[index + 1] - ticks[index] not in (0, 1)
                or irq_delta != 1):
            raise ValueError(f"{path}: discontinuity after refresh {index}")
    if ticks[-1] - ticks[-2] != 1:
        raise ValueError(f"{path}: end the window on an advancing refresh")
    updates = []
    for tick, identical in groupby(rows, key=lambda row: int(row["tick"])):
        if tick == ticks[-1]:
            break
        group = list(identical)
        published = [int(row["pending"], 16) == LIST_PUBLISHED for row in group]
        if len(group) > 2 or published != [False] * (len(group) - 1) + [True] or any(
            row["ready"] != "1" for row in group
        ):
            raise ValueError(f"{path}: unexpected publication cadence at gameplay tick {tick}")
        complete = group[-1]
        draw = {field: int(complete[field]) for field in
                ("draws", "visible_draws", "blended_draws", "upload_bytes", *DRAW_PHASES, *SIM_PHASES)}
        draw["offscreen_draws"] = draw["draws"] - draw["visible_draws"]
        draw["draw_ms"] = sum(draw[key] for key in DRAW_PHASES)
        draw["simulation_ms"] = sum(draw[key] for key in SIM_PHASES)
        # Use the first IRQ timestamp for this update even if it missed a refresh.
        draw["elapsed_ms"] = (int(complete["profile_tmu"]) - int(group[0]["irq_tmu"])) & 0xFFFFFFFF
        draw["same_timer_tick_as_deadline"] = complete["profile_tmu"] == group[0]["tmu"]
        draw["hold"] = len(group) == 2
        updates.append(draw)
    return Route(name or window, ticks, updates)


def matrix(route, fields):
    return np.array([[row[field] for field in fields] for row in route.updates], dtype=float)


def linear_fit(counts, targets):
    center = counts.mean(axis=0)
    scale = np.maximum(counts.std(axis=0), 1)
    coefficients, *_ = np.linalg.lstsq((counts - center) / scale, targets - targets.mean(), rcond=None)
    coefficients = coefficients / scale
    return coefficients, targets.mean() - center @ coefficients


def fit(train, fields):
    counts = matrix(train, fields)
    draw_time = matrix(train, ("draw_ms",)).ravel()
    coefficients, intercept = linear_fit(counts, draw_time)
    predicted_draw = intercept + counts @ coefficients
    simulation = matrix(train, ("simulation_ms",)).ravel()
    elapsed = matrix(train, ("elapsed_ms",)).ravel()
    fixed_work = (elapsed - predicted_draw - simulation).mean()
    return coefficients, intercept, fixed_work


def score(route, estimates):
    predictions = predict(estimates, IRQ_PERIOD_MS)
    report = compare({route.name: route.ticks}, {route.name: predictions}, "diagnostic")
    held = [float(estimate) >= IRQ_PERIOD_MS for estimate in estimates]
    actual = [row["hold"] for row in route.updates]
    return {
        "hits": sum(x and y for x, y in zip(held, actual)),
        "missed_holds": sum(y and not x for x, y in zip(held, actual)),
        "extra_holds": sum(x and not y for x, y in zip(held, actual)),
        **{k: report[k] for k in ("matched_events", "missed_events", "extra_events", "score_percent")},
    }


def test_model(model, fields, route):
    coefficients, intercept, fixed_work = model
    estimate_draw = intercept + matrix(route, fields) @ coefficients
    measured_draw = matrix(route, ("draw_ms",)).ravel()
    estimated_total = estimate_draw + matrix(route, ("simulation_ms",)).ravel() + fixed_work
    # Previous-update diagnostic. The first update has no prior measurement.
    lag = np.concatenate(([0], estimated_total[:-1]))
    return {
        "draw_mae_ms": round(float(np.mean(abs(estimate_draw - measured_draw))), 3),
        "same_tick": score(route, estimated_total),
        "previous_tick": score(route, lag),
    }


def aligned_ee(path, route):
    samples = stock_counts(path, len(route.updates), CYCLE_HEADER)
    # The recorder labels the work with the tick before simulation. Match
    # the work already finished when MAME samples its tick at the video IRQ.
    return np.asarray(samples[2 * HISTORY - 1:-1], dtype=float)[:, :2]


def test_ee_bridge(train, test, train_ee, test_ee):
    phases = ("simulation_ms", "draw_ms")
    native_train = matrix(train, phases)
    native_test = matrix(test, phases)
    estimates = []
    accuracy = {}
    for col, phase in enumerate(phases):
        coefficient, intercept = linear_fit(train_ee[:, col:col + 1], native_train[:, col])
        predicted = intercept + coefficient[0] * test_ee[:, col]
        estimates.append(predicted)
        accuracy[phase] = round(float(np.mean(abs(predicted - native_test[:, col]))), 3)
    fixed_work = (matrix(train, ("elapsed_ms",)).ravel() - native_train.sum(axis=1)).mean()
    estimated_total = sum(estimates) + fixed_work
    return {"phase_mae_ms": accuracy, "same_tick": score(test, estimated_total)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bond", type=Path)
    parser.add_argument("dyne", type=Path)
    parser.add_argument("quiet", type=Path)
    parser.add_argument("--holdout", nargs=2, action="append", default=[], metavar=("NAME", "TRACE"))
    parser.add_argument("--ee-cycles", nargs=2, type=Path, metavar=("BOND", "DYNE"),
                        help="optional release- and Rose Pod-aligned stock S01 cycle captures")
    args = parser.parse_args()
    try:
        bond, dyne, quiet = map(read_route, (args.bond, args.dyne, args.quiet))
        holdouts = [quiet, *(read_route(Path(path), name) for name, path in args.holdout)]
        named_routes = [bond, dyne, *holdouts]
        if len({route.name for route in named_routes}) != len(named_routes):
            raise ValueError("use distinct names for the capture windows")
        ee = dict(zip((bond.name, dyne.name),
                      (aligned_ee(path, route) for path, route in zip(args.ee_cycles or (), (bond, dyne)))))
        folds = {}
        for train, test in ((bond, dyne), (dyne, bond)):
            fold = {}
            for family, fields in COST_FEATURES.items():
                model = fit(train, fields)
                fold[family] = {
                    "fit_arcade_ms_per_unit": dict(zip(fields, model[0].tolist())),
                    "held_out": test_model(model, fields, test),
                    "controls": {r.name: test_model(model, fields, r) for r in holdouts},
                }
            if ee:
                fold["ps2_ee_bridge"] = test_ee_bridge(train, test, ee[train.name], ee[test.name])
            folds[f"{train.name} -> {test.name}"] = fold
        diagnostics = {}
        for route in named_routes:
            diagnostics[route.name] = {
                "native_elapsed": score(route, matrix(route, ("elapsed_ms",)).ravel()),
                "timer_ties": {
                    "advance": sum(row["same_timer_tick_as_deadline"] and not row["hold"] for row in route.updates),
                    "hold": sum(row["same_timer_tick_as_deadline"] and row["hold"] for row in route.updates),
                },
                "median": {
                    label: {field: median(row[field] for row in route.updates if row["hold"] == hold)
                            for field in ("draws", "draw_ms", "simulation_ms", "elapsed_ms")}
                    for label, hold in (("advance", False), ("hold", True))
                    if any(row["hold"] == hold for row in route.updates)
                },
            }
    except (OSError, KeyError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({"folds": folds, "diagnostics": diagnostics}, indent=2))


if __name__ == "__main__":
    main()
