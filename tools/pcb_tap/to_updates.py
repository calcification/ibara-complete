#!/usr/bin/env python3
"""Turn a tap recording (one input word per PCB refresh) plus the capture's held frames into one input word per
game update, for tools/pcb_tap/mame_replay.lua. Standard library only.

    python3 to_updates.py run1.tap run1.frames --out run1.updates [--offset N] [--lag 1] [--max-run 2]

* --offset: capture frame index of tap frame 0 (default: the first non-blank captured frame).
* A repeated frame counts as a held update only inside runs of at most --max-run repeats; longer runs are a still
  picture (menus, pauses), not slowdown.
* --lag: refreshes between the vsync at which an update read its inputs and the refresh where its picture first
  shows (1 by default; check it with the replay: a wrong lag drifts the ship by one frame of movement).

Output: "# ..." header, then per game update "update pcb_frame holds_before hexbits".
"""
from __future__ import annotations

import argparse


def read_frames(path):
    flags = []
    for line in open(path):
        if line.startswith("#") or not line.strip():
            continue
        flags.append(line.split()[2])
    return flags


def read_tap(path):
    out = []
    for line in open(path):
        if line.startswith("#") or not line.strip():
            continue
        out.append(int(line.split()[1], 16))
    return out


def classify(flags, max_run=2):
    """Per captured frame: 'B' blank, 'H' held update, 'A' advanced (new picture or a still scene)."""
    out = []
    i, n = 0, len(flags)
    while i < n:
        if flags[i] != "1":
            out.append("B" if flags[i] == "B" else "A")
            i += 1
            continue
        j = i
        while j < n and flags[j] == "1":
            j += 1
        out.extend(("H" if j - i <= max_run else "A") for _ in range(i, j))
        i = j
    return out


def to_updates(tap, flags, offset=None, lag=1, max_run=2):
    """[(update, pcb_frame, holds_before, bits)] - pcb_frame counts tap frames (vsyncs since power-on)."""
    cls = classify(flags, max_run)
    if offset is None:
        offset = next(i for i, c in enumerate(cls) if c != "B")
    rows, holds, update = [], 0, 0
    for frame in range(len(tap)):
        v = frame + offset
        if v >= len(cls):
            break
        c = cls[v]
        if c == "H":
            holds += 1
            continue
        src = min(len(tap) - 1, max(0, frame - lag))
        rows.append((update, frame, holds, tap[src]))
        update += 1
        holds = 0
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tap")
    ap.add_argument("frames")
    ap.add_argument("--out", required=True)
    ap.add_argument("--offset", type=int)
    ap.add_argument("--lag", type=int, default=1)
    ap.add_argument("--max-run", type=int, default=2)
    args = ap.parse_args(argv)
    tap, flags = read_tap(args.tap), read_frames(args.frames)
    nonblank = sum(1 for f in flags if f != "B")
    if abs(nonblank - len(tap)) > 2:
        print(f"warning: {nonblank} non-blank captured frames vs {len(tap)} tap frames: the capture dropped or "
              "repeated frames, or the recordings cover different spans")
    rows = to_updates(tap, flags, args.offset, args.lag, args.max_run)
    with open(args.out, "w") as out:
        out.write(f"# from {args.tap} + {args.frames} lag {args.lag} max-run {args.max_run}\n")
        for r in rows:
            out.write("%d %d %d %03x\n" % r)
    held = sum(r[2] for r in rows)
    print(f"{len(rows)} updates, {held} held refreshes -> {args.out}")


if __name__ == "__main__":
    main()
