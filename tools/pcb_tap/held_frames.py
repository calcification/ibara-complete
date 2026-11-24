#!/usr/bin/env python3
"""Find held (repeated) frames in a progressive capture of the PCB's video. Needs ffmpeg and numpy.

    python3 held_frames.py capture.mkv --crop 240:320:40:0 --out run1.frames

Output, one line per captured frame: "index diff flag", flag 1 = the frame repeats the previous one (the game held
an update), 0 = it advanced, B = blank (no signal yet). Use a crop over the playfield only (no scores). The capture
must deliver every one of the board's 60.024 Hz frames once: compare the non-blank frame count with the tap's
vsync count for the same span before trusting the result (README).
"""
from __future__ import annotations

import argparse
import subprocess


def frame_diffs(path, crop):
    import numpy as np
    w, h, x, y = (int(v) for v in crop.split(":"))
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-vf", f"crop={w}:{h}:{x}:{y},format=gray", "-f", "rawvideo", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    prev = None
    while True:
        buf = proc.stdout.read(w * h)
        if len(buf) < w * h:
            break
        cur = np.frombuffer(buf, dtype=np.uint8).astype(np.int16)
        mean = float(cur.mean())
        diff = None if prev is None else float(np.abs(cur - prev).mean())
        yield mean, diff
        prev = cur
    proc.wait()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--crop", required=True, metavar="W:H:X:Y")
    ap.add_argument("--out", required=True)
    ap.add_argument("--held-below", type=float, default=0.5, help="mean |diff| treated as a repeat (capture noise)")
    ap.add_argument("--blank-below", type=float, default=4.0, help="mean luma treated as no signal")
    args = ap.parse_args(argv)
    n = held = 0
    with open(args.out, "w") as out:
        out.write(f"# {args.video} crop {args.crop} held<{args.held_below}\n")
        for i, (mean, diff) in enumerate(frame_diffs(args.video, args.crop)):
            if mean < args.blank_below:
                flag = "B"
            else:
                flag = "1" if diff is not None and diff < args.held_below else "0"
                n += 1
                held += flag == "1"
            out.write(f"{i} {diff if diff is not None else -1:.3f} {flag}\n")
    print(f"{n} non-blank frames, {held} repeats -> {args.out}")


if __name__ == "__main__":
    main()
