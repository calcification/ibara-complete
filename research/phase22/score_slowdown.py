#!/usr/bin/env python3
"""Compare aligned, per-refresh retail Arcade timing traces."""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
import json
from pathlib import Path

ONSET_TOLERANCE = 4
ADVANCES_BETWEEN_HOLDS = 4


@dataclass
class Slowdown:
    onset: int
    last_hold: int
    held_refreshes: int = 1


def read_trace(path: Path) -> dict[str, list[int]]:
    windows: dict[str, list[int]] = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not {"window", "frame", "tick"} <= set(reader.fieldnames or []):
            raise ValueError(f"{path}: expected window,frame,tick columns")
        for row in reader:
            where = f"{path}:{reader.line_num}"
            window = (row["window"] or "").strip()
            try:
                frame, tick = int(row["frame"]), int(row["tick"])
            except (TypeError, ValueError) as err:
                raise ValueError(f"{where}: frame and tick must be integers") from err
            if not window or tick < 0:
                raise ValueError(f"{where}: window must be named and tick must be nonnegative")
            ticks = windows.setdefault(window, [])
            if frame != len(ticks):
                raise ValueError(f"{where}: window {window!r} needs consecutive frames from 0")
            if ticks and tick - ticks[-1] not in (0, 1):
                raise ValueError(f"{where}: expected zero or one gameplay update per refresh")
            ticks.append(tick)
    if not windows:
        raise ValueError(f"{path}: trace has no timing rows")
    for window, ticks in windows.items():
        if len(ticks) < 2 or ticks[-1] - ticks[-2] != 1:
            raise ValueError(f"{path}: window {window!r} must end on an advancing refresh")
    return windows


def slowdowns(ticks: list[int]) -> list[Slowdown]:
    events: list[Slowdown] = []
    for frame in range(1, len(ticks)):
        if ticks[frame] != ticks[frame - 1]:
            continue
        if events and frame - events[-1].last_hold - 1 <= ADVANCES_BETWEEN_HOLDS:
            events[-1].last_hold = frame
            events[-1].held_refreshes += 1
        else:
            events.append(Slowdown(frame, frame))
    return events


def matching_pairs(reference: list[Slowdown], candidate: list[Slowdown]) -> list[tuple[int, int]]:
    # Maximize ordered one-to-one matches, then prefer smaller onset and hold-count errors.
    scores = [[(0, 0, 0)] * (len(candidate) + 1) for _ in range(len(reference) + 1)]
    for i, before in enumerate(reference, 1):
        for j, after in enumerate(candidate, 1):
            scores[i][j] = max(scores[i - 1][j], scores[i][j - 1])
            onset_error = abs(after.onset - before.onset)
            hold_error = abs(after.held_refreshes - before.held_refreshes)
            if onset_error <= ONSET_TOLERANCE and hold_error * 5 <= before.held_refreshes:
                count, onset_cost, hold_cost = scores[i - 1][j - 1]
                scores[i][j] = max(scores[i][j], (count + 1, onset_cost - onset_error, hold_cost - hold_error))

    pairs = []
    i, j = len(reference), len(candidate)
    while i and j:
        if scores[i][j] == scores[i][j - 1]:
            j -= 1
        elif scores[i][j] == scores[i - 1][j]:
            i -= 1
        else:
            pairs.append((i - 1, j - 1))
            i -= 1
            j -= 1
    return pairs[::-1]


def compare(reference: dict[str, list[int]], candidate: dict[str, list[int]], reference_kind: str) -> dict:
    if reference.keys() != candidate.keys():
        raise ValueError("reference and candidate need the same named windows")
    windows = {}
    match_count = miss_count = extra_count = 0
    for name, before_ticks in reference.items():
        after_ticks = candidate[name]
        logical_duration = before_ticks[-1] - before_ticks[0]
        if logical_duration != after_ticks[-1] - after_ticks[0]:
            raise ValueError(f"window {name!r} needs the same number of gameplay updates in both traces")
        before, after = slowdowns(before_ticks), slowdowns(after_ticks)
        pairs = matching_pairs(before, after)
        matches = [{"reference": asdict(before[i]), "candidate": asdict(after[j])} for i, j in pairs]
        used_before, used_after = {i for i, _ in pairs}, {j for _, j in pairs}
        misses = [asdict(event) for i, event in enumerate(before) if i not in used_before]
        extras = [asdict(event) for j, event in enumerate(after) if j not in used_after]
        match_count += len(matches)
        miss_count += len(misses)
        extra_count += len(extras)
        first_difference = next(
            (frame for frame, (ref_tick, candidate_tick) in enumerate(zip(before_ticks, after_ticks))
             if ref_tick - before_ticks[0] != candidate_tick - after_ticks[0]),
            None,
        )
        windows[name] = {
            "gameplay_updates": logical_duration,
            "first_cadence_difference": first_difference,
            "matches": matches,
            "misses": misses,
            "extras": extras,
        }

    total = match_count + miss_count + extra_count
    reference_has_slowdown = match_count + miss_count > 0
    return {
        "reference_kind": reference_kind,
        "score_percent": round(100 * match_count / total, 2) if total else None,
        "meets_pcb_80_percent_target": (
            match_count * 5 >= total * 4 if reference_kind == "pcb" and reference_has_slowdown else None
        ),
        "matched_events": match_count,
        "missed_events": miss_count,
        "extra_events": extra_count,
        "windows": windows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--reference-kind", choices=("pcb", "diagnostic"), required=True)
    args = parser.parse_args()
    try:
        report = compare(read_trace(args.reference), read_trace(args.candidate), args.reference_kind)
    except (OSError, ValueError) as err:
        parser.error(str(err))
    print(json.dumps(report, indent=2))
    if args.reference_kind == "pcb":
        return 0 if report["meets_pcb_80_percent_target"] is True else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
