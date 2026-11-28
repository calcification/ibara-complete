#!/usr/bin/env python3
"""Locate Stage 1 differences in two release replay probe savestates."""
import argparse
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from p2s_tools import load_ee

HEADER = 0x01700000
TRACE = 0x01E00000
UPDATES = 1200
ROW = struct.Struct("<30I")
FIELDS = (
    "marker", "tick", "seed", "score", "x", "y", "input",
    "script", "scroll", "slot_flags", "slot_type",
    "factory_calls", "created", "resident_checks", "ready", "pool_checks", "allocated",
    "gate_calls", "gate_ready", "gate_status", "rng_count", "rng_order",
)


def parse(memory, side, count):
    base = TRACE + side * UPDATES * ROW.size
    rows = []
    for i in range(count):
        values = ROW.unpack_from(memory, base + i * ROW.size)
        if values[0] != i + 1:
            raise ValueError(f"missing side {side} trace at update {i}")
        row = dict(zip(FIELDS, values))
        row["rng_callers"] = [f"0x{caller:08X}" for caller in values[len(FIELDS):][:row["rng_count"]]]
        rows.append(row)
    return rows


def factory(rows):
    attempts = [(i, row) for i, row in enumerate(rows) if row["factory_calls"]]
    return dict(first_attempt=attempts[0][0] if attempts else None,
                creation=[i for i, row in attempts if row["created"]],
                retries=[i for i, row in attempts if not row["created"]],
                resource_failures=sum(row["resident_checks"] - row["ready"] for _, row in attempts),
                pool_failures=sum(row["pool_checks"] - row["allocated"] for _, row in attempts))


def gate(rows):
    attempts = [(i, row) for i, row in enumerate(rows) if row["gate_calls"]]
    statuses = []
    for i, row in attempts:
        status = f"0x{row['gate_status']:04X}"
        if not statuses or statuses[-1]["value"] != status:
            statuses.append(dict(update=i, value=status))
    return dict(first_attempt=attempts[0][0] if attempts else None,
                first_ready=next((i for i, row in attempts if row["gate_ready"]), None),
                advanced=next((i for i, row in attempts if i + 1 < len(rows)
                               and rows[i + 1]["script"] != row["script"]), None),
                status_changes=statuses)


def compare(record, playback, symbols, limit=None):
    magic, _, version, header, size, updates = struct.unpack_from("<6I", record, HEADER)
    if magic != 0x42464249 or version != 3 or header != 1416 or not updates:
        raise ValueError("expected a saved format 3 replay")
    end = HEADER + header + size
    if record[HEADER:end] != playback[HEADER:end]:
        raise ValueError("the two captures contain different replay files")
    played, flags, errors = struct.unpack_from("<3I", playback, symbols["rpl_stat"])
    if played != updates or errors:
        raise ValueError(f"played {played} of {updates} updates with {errors} decode errors")
    count = min(updates, UPDATES, limit if limit is not None else UPDATES)
    before, after = parse(record, 0, count), parse(playback, 1, count)
    differences = {}
    for i, (a, b) in enumerate(zip(before, after)):
        for key in a:
            if a[key] != b[key] and key not in differences:
                differences[key] = dict(update=i, record=a[key], playback=b[key])
    control = {name: struct.unpack_from("<I", playback, symbols[f"drift_gate_{name}"])[0]
               for name in ("target", "holds", "blocks")}
    return dict(updates=count, first_differences=differences, control=control,
                record_gate=gate(before), play_gate=gate(after), record_factory=factory(before),
                play_factory=factory(after), end_mismatch_flags=flags)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    parser.add_argument("playback", type=Path)
    parser.add_argument("symbols", type=Path)
    parser.add_argument("--updates", type=int, choices=range(1, UPDATES + 1), metavar="COUNT")
    args = parser.parse_args()
    try:
        symbols = json.loads(args.symbols.read_text())
        result = compare(load_ee(args.record), load_ee(args.playback), symbols, args.updates)
    except (KeyError, struct.error, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
