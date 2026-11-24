#!/usr/bin/env python3
"""Compare the PCB's held refreshes with MAME's for the same game updates (tools/pcb_tap). Standard library only.

    python3 compare.py run1.updates run1.mame [--window 300] [--from-update N]

run1.updates: to_updates.py output (PCB holds before each update). run1.mame: mame_replay.lua output.
Prints holds per window of updates on both machines and how many PCB hold events MAME reproduces at the same
update (exactly, or one update away).
"""
from __future__ import annotations

import argparse


def pcb_holds(path):
    out = []
    for line in open(path):
        if line.startswith("#") or not line.strip():
            continue
        out.append(int(line.split()[2]))
    return out


def mame_holds(path):
    """Holds before each update, counted from the first update the replay applied."""
    out, holds, started = [], 0, False
    for line in open(path):
        if line.startswith("#") or not line.strip():
            continue
        advanced = int(line.split()[2])
        if advanced:
            if started:
                out.append(holds)
            started, holds = True, 0
        elif started:
            holds += 1
    return out


def compare(pcb, mame, window=300, start=0):
    n = min(len(pcb), len(mame))
    rows = []
    for w in range(start, n, window):
        e = min(n, w + window)
        rows.append((w, e, sum(pcb[w:e]), sum(mame[w:e])))
    events = [i for i in range(start, n) if pcb[i]]
    exact = sum(1 for i in events if mame[i])
    near = sum(1 for i in events if any(0 <= j < n and mame[j] for j in (i - 1, i, i + 1)))
    extra = sum(1 for i in range(start, n) if mame[i] and not any(0 <= j < n and pcb[j] for j in (i - 1, i, i + 1)))
    return rows, len(events), exact, near, extra


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("updates")
    ap.add_argument("mame")
    ap.add_argument("--window", type=int, default=300)
    ap.add_argument("--from-update", type=int, default=0)
    args = ap.parse_args(argv)
    rows, events, exact, near, extra = compare(pcb_holds(args.updates), mame_holds(args.mame), args.window,
                                               args.from_update)
    print("updates            PCB holds  MAME holds")
    for w, e, p, m in rows:
        if p or m:
            print(f"{w:7d}-{e:<7d}     {p:6d}      {m:6d}")
    if events:
        print(f"PCB hold events {events}: MAME at the same update {exact} ({exact / events:.0%}), within one update "
              f"{near} ({near / events:.0%}); MAME-only holds {extra}")
    else:
        print(f"no PCB holds in range; MAME-only holds {extra}")


if __name__ == "__main__":
    main()
