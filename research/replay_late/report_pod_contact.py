#!/usr/bin/env python3
"""Compare pod projectiles and enemy slot 3 immediately before collision."""
import argparse
from itertools import zip_longest
import json
from pathlib import Path
import struct

from report_events import ROWS as EVENT_ROWS
from report_events import START, decode, load_ee, read_side

BASE = 0x01660000
ROWS = 768
FIRST = 2000
ROW = struct.Struct("<708I")
SHOT_WORDS = 13
SHOT_COUNT = 48
POD_WORDS = 36
ENEMY_WORDS = 45
ACTIVE = 0x08000000
CANDIDATES = struct.Struct("<769I")
CANDIDATE_ROWS = 8
CANDIDATE_BASE = BASE + 2 * ROWS * ROW.size
SHOT_FIELDS = {0: "flags", 1: "kind", 2: "animation", 3: "cel", 4: "x", 5: "y"}
ENEMY_FIELDS = {0: "flags", 1: "kind", 7: "hitbox", 9: "x", 10: "y", 15: "hp",
                42: "collision_gate"}


def named_diff(a, b, names=None):
    names = names or {}
    return {names.get(i, f"+0x{4*i:02x}"): [f"{x:#010x}", f"{y:#010x}"]
            for i, (x, y) in enumerate(zip(a, b)) if x != y}


def read_rows(memory, side):
    result = {}
    for index in range(ROWS):
        saved = ROW.unpack_from(memory, BASE + (side * ROWS + index) * ROW.size)
        present, tick, score = saved[:3]
        if (present & 0xFFFF, tick >> 24) != (1, 2):
            raise ValueError(f"missing Stage 1 pod row {index} for side {side}")
        pods = saved[3:3 + POD_WORDS]
        shots = saved[3 + POD_WORDS:-ENEMY_WORDS]
        shots = [shots[i:i + SHOT_WORDS] for i in range(0, len(shots), SHOT_WORDS)]
        update = FIRST + index - 1 if index else 0
        result[update] = dict(tick=tick, score=score, cursor=present >> 16, pods=pods,
                              shots=shots, enemy=saved[-ENEMY_WORDS:])
    return result


def first_shot_difference(a, b, only_slot=None, through=None):
    for update, before in a.items():
        if through is not None and update > through:
            break
        for i, (x, y) in enumerate(zip(before["shots"], b[update]["shots"])):
            if only_slot is not None and i != only_slot:
                continue
            if (x[0] | y[0]) & ACTIVE and x[:6] != y[:6]:
                return dict(update=update, slot=i, changes=named_diff(x, y, SHOT_FIELDS))
    return None


def summarize_shot(row, slot):
    if not 0 <= slot < SHOT_COUNT:
        return None
    shot = row["shots"][slot]
    return {name: f"{shot[i]:#010x}" for i, name in SHOT_FIELDS.items()}


def first_hit_difference(memory, first, a, b):
    events = [read_side(memory, side, first) for side in range(2)]
    window = range(first, first + EVENT_ROWS)
    if any(side.keys() != set(window) for side in events):
        raise ValueError("expected both complete pod event windows")
    if any(update not in a for update in window):
        raise ValueError("event window falls outside the pod samples")
    for update in window:
        hits = [[event for event in side[update][1] if event[0] & 0xFFFF == 6] for side in events]
        for record, play in zip_longest(*hits):
            if record == play:
                continue
            slot = (record or play)[1]
            left, right = a[update], b[update]
            same_slot = [summarize_shot(side, slot) for side in (left, right)]
            return dict(update=update, events=[decode(e) if e else None for e in (record, play)],
                        first_collision_field_difference=first_shot_difference(a, b, slot, update),
                        same_slot_at_contact=same_slot,
                        target_slot_3_changes=named_diff(left["enemy"], right["enemy"], ENEMY_FIELDS))
    return None



def candidate_rows(memory, side):
    for i in range(CANDIDATE_ROWS):
        words = CANDIDATES.unpack_from(memory, CANDIDATE_BASE + (side * CANDIDATE_ROWS + i) * CANDIDATES.size)
        if words[0]:
            yield words[0] - 1, {slot: words[j:j + 4] for slot, j in enumerate(range(1, len(words), 4))
                                  if words[j] & 0x02000000}


def compare_candidates(memory):
    a, b = (dict(candidate_rows(memory, side)) for side in range(2))
    shared = sorted(a.keys() & b.keys())
    return dict(updates=shared, flags_kind_position_match=all(a[i] == b[i] for i in shared) if shared else None,
                first_difference=next((i for i in shared if a[i] != b[i]), None))


def target_selection(row):
    return [dict(current=row["pods"][pod * 12 + 9] & 0xFFFF,
                 desired=row["pods"][pod * 12 + 9] >> 16,
                 target=row["pods"][pod * 12 + 10] & 0xFFFF)
            for pod in range(3)]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state", type=Path)
    parser.add_argument("symbols", type=Path)
    args = parser.parse_args()
    syms = json.loads(args.symbols.read_text())
    if "replay_contact_entry" not in syms:
        parser.error("use symbols from a --pod-contact fixture")
    memory = load_ee(args.state)
    a, b = (read_rows(memory, side) for side in range(2))
    first_symbol = syms.get("replay_late_window_start")
    event_first = struct.unpack_from("<I", memory, first_symbol)[0] if first_symbol is not None else START
    shot_difference = first_shot_difference(a, b)
    result = dict(window=[FIRST, FIRST + ROWS - 2], first_active_shot_difference=shot_difference,
                  entry_target_search_cursor=[a[0]["cursor"], b[0]["cursor"]],
                  cursor_at_first_active_shot_difference=(
                      [side[shot_difference["update"]]["cursor"] for side in (a, b)] if shot_difference else None),
                  aim_at_first_active_shot_difference=(
                      [target_selection(side[shot_difference["update"]]) for side in (a, b)]
                      if shot_difference else None),
                  initial_candidates=compare_candidates(memory),
                  first_pod_record_difference=next((dict(update=i, changes=named_diff(x["pods"], b[i]["pods"]))
                                                   for i, x in a.items() if x["pods"] != b[i]["pods"]), None),
                  first_target_difference=next((dict(update=i, changes=named_diff(x["enemy"], b[i]["enemy"], ENEMY_FIELDS))
                                                for i, x in a.items() if x["enemy"] != b[i]["enemy"]), None),
                  first_pod_hit_difference=first_hit_difference(memory, event_first, a, b))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
