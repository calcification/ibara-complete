#!/usr/bin/env python3
"""Compare the ordered Noir Stage 1 graze, damage and RNG replay trace."""
import argparse
from collections import Counter
from itertools import zip_longest
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "phase45"))
from report_trace import analyze, load_ee

BASE = 0x01EC0000
START = 1000
ROWS = 128
MAX_EVENTS = 8064
WORDS = struct.Struct("<4I")
SIDE_SIZE = (ROWS + MAX_EVENTS) * WORDS.size
NAMES = {1: "rng", 2: "damage", 3: "graze_test", 4: "xtc_graze", 5: "retail_graze"}


def signed(word):
    return (word ^ 0x80000000) - 0x80000000


def decode(event):
    tag, a, b, c = event
    name = NAMES[tag & 0xFFFF]
    out = dict(event=name, between_updates=bool(tag >> 16))
    if name == "rng":
        out.update(site=f"{a:#010x}", limit=b, seed=f"{c:#010x}")
    elif name == "damage":
        amount = (b >> 8) & 0xFFFF
        out.update(site=f"{a:#010x}", slot=b & 0xFF, amount=(amount ^ 0x8000) - 0x8000,
                   killed=bool(b >> 24), hp_before=c & 0xFFFF, hp_after=c >> 16)
    elif name == "graze_test":
        out.update(side=(a & 0xFF) + 1, shot_held=(a >> 8) & 0xFF, pods=a >> 16, flags=f"{b:#010x}")
    elif name == "retail_graze":
        out.update(site=f"{a:#010x}", side=(b & 0xFF) + 1, slot=b >> 8, score=c)
    else:
        out.update(bullet=a & 0xFF, half_width=(a >> 8) & 0xFF, half_height=a >> 16,
                   dx=signed(b), dy=signed(c))
    return out


def read_side(mem, side, first_update=START):
    result = {}
    start = BASE + side * SIDE_SIZE
    event_base = start + ROWS * WORDS.size
    used = 0
    for i in range(ROWS):
        tick, first, count, dropped = WORDS.unpack_from(mem, start + i * WORDS.size)
        if not tick:
            continue
        if first != used or count > MAX_EVENTS - used or dropped or tick >> 24 != 2:
            raise ValueError(f"invalid or truncated trace at update {first_update + i}, side {side}")
        events = [WORDS.unpack_from(mem, event_base + j * WORDS.size) for j in range(first, first + count)]
        used += count
        result[first_update + i] = (tick, events)
    return result


def compare_events(mem, first_update=START):
    a, b = read_side(mem, 0, first_update), read_side(mem, 1, first_update)
    end = first_update + ROWS - 1
    expected = set(range(first_update, end + 1))
    if a.keys() != expected or b.keys() != expected:
        raise ValueError(f"expected both full Stage 1 event traces through update {end}")
    counts = []
    for side in (a, b):
        seen = Counter(NAMES[e[0] & 0xFFFF] for _, events in side.values() for e in events)
        counts.append({name: seen[name] for name in NAMES.values()})
    differences = []
    first_by_kind = {}
    for update in sorted(expected):
        tick_a, events_a = a[update]
        tick_b, events_b = b[update]
        if tick_a != tick_b:
            differences.append(dict(update=update, stage_tick=[tick_a, tick_b]))
        for index, (ea, eb) in enumerate(zip_longest(events_a, events_b)):
            if ea != eb:
                differences.append(dict(update=update, ordinal=index,
                                        record=decode(ea) if ea else None, playback=decode(eb) if eb else None))
                break
        for tag, name in NAMES.items():
            sig_a = [e for e in events_a if e[0] & 0xFFFF == tag]
            sig_b = [e for e in events_b if e[0] & 0xFFFF == tag]
            if sig_a != sig_b and name not in first_by_kind:
                first_by_kind[name] = dict(update=update, record=[decode(e) for e in sig_a],
                                           playback=[decode(e) for e in sig_b])
    return dict(window=[first_update, end], counts=counts,
                updates_with_event_differences=len({d["update"] for d in differences}),
                first_event_difference=differences[0] if differences else None, first_by_kind=first_by_kind)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state", type=Path)
    parser.add_argument("symbols", type=Path)
    parser.add_argument("--require-match", action="store_true", help="fail on any gameplay or event divergence")
    args = parser.parse_args()
    symbols = json.loads(args.symbols.read_text())
    if "replay_late_begin" not in symbols:
        parser.error("use symbols from a --late-trace fixture")
    try:
        mem = load_ee(args.state)
        checkpoints = analyze(mem, symbols["rp"], False)
        start_symbol = symbols.get("replay_late_window_start")
        start = START if start_symbol is None else struct.unpack_from("<I", mem, start_symbol)[0]
        report = dict(checkpoints, **compare_events(mem, start))
    except (ValueError, struct.error, KeyError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2))
    return int(args.require_match and bool(report["mismatches"] or report["tick_miss"]
                                           or report["updates_with_event_differences"]))


if __name__ == "__main__":
    sys.exit(main())
