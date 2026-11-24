#!/usr/bin/env python3
"""Score completed PS2 work as a predictor of MAME slowdown on unseen routes."""

import argparse
import json
from pathlib import Path
from statistics import median

from assess_budget import read_quiet
from assess_workload import HISTORY, Route, fit, predict, report, stock_counts
from score_slowdown import read_trace, slowdowns
from workload_capture import CYCLE_HEADER


def signals(samples):
    result = {key: list(values) for key, values in zip(CYCLE_HEADER, zip(*samples))}
    result["sim_and_draw_counts"] = [sim + draw for sim, draw, _ in samples]
    for key, values in list(result.items()):
        result[f"{key}_avg8"] = [sum(values[max(0, i - HISTORY + 1):i + 1]) // min(i + 1, HISTORY)
                                for i in range(len(values))]
    return result


def prepare_route(name, reference, stock):
    ticks = read_trace(reference)[name]
    samples = stock_counts(stock, ticks[-1] - ticks[0], CYCLE_HEADER)
    # A workload row names the tick before the measured work runs. The previous
    # row's measurements are available to a native decision at the current tick.
    previous = slice(2 * HISTORY - 1, -1)
    return Route(name, ticks, samples[previous],
                 {key: values[previous] for key, values in signals(samples).items()})


def medians(route):
    held = {a - route.ticks[0] for a, b in zip(route.ticks, route.ticks[1:]) if a == b}
    result = {}
    for key, values in route.signals.items():
        if key.endswith("_avg8"):
            continue
        advancing = [value for tick, value in enumerate(values) if tick not in held]
        holding = [value for tick, value in enumerate(values) if tick in held]
        result[key] = {"advance": median(advancing) if advancing else None,
                       "hold": median(holding) if holding else None}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", nargs=3, required=True, metavar=("NAME", "MAME", "STOCK"))
    parser.add_argument("--quiet", type=Path, required=True, help="stock Stage 1 workload CSV with cycle columns")
    args = parser.parse_args()
    if len(args.case) < 2 or len({case[0] for case in args.case}) != len(args.case):
        parser.error("supply at least two distinct named cases")
    try:
        routes = [prepare_route(name, Path(mame), Path(stock)) for name, mame, stock in args.case]
        quiet = signals(read_quiet(args.quiet, CYCLE_HEADER))
        folds = []
        for holdout in routes:
            training = [route for route in routes if route is not holdout]
            rule = fit(training)
            key, threshold = rule
            quiet_ticks = predict(quiet[key], threshold)
            folds.append({"training": report(training, rule), "held_out": report([holdout], rule),
                          "stage1_events": len(slowdowns(quiet_ticks)),
                          "stage1_holds": len(quiet_ticks) - len(quiet[key]) - 1})
    except (KeyError, OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({"medians": {r.name: medians(r) for r in routes}, "folds": folds}, indent=2))


if __name__ == "__main__":
    main()
