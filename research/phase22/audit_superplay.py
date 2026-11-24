#!/usr/bin/env python3
"""Locate sustained alternate-field repeats in original interlaced NTSC footage."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile

import numpy as np


FIELD_PTS = 3003  # 90 kHz picture clock doubled by FFmpeg's separatefields filter


def crop_argument(value):
    try:
        width, height, x, y = map(int, value.split(":"))
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected width:height:x:y") from error
    if width < 16 or height < 20:
        raise argparse.ArgumentTypeError("crop must be at least 16 by 20")
    if min(x, y) < 0 or width % 2 or height % 4 or x % 2 or y % 2:
        raise argparse.ArgumentTypeError("use an even nonnegative x and y, an even width, and a height divisible by four")
    return width, height, x, y


def decode_fields(path, crop):
    width, height, x, y = crop
    command = [
        "ffmpeg", "-hide_banner", "-nostdin", "-copyts", "-i", str(path),
        "-map", "0:v:0", "-an", "-sn", "-vf",
        f"showinfo@pictures,crop={width}:{height}:{x}:{y},separatefields,"
        f"scale={width // 2}:{height // 4}:flags=area,format=gray,showinfo@fields",
        "-fps_mode", "passthrough", "-f", "rawvideo", "pipe:1",
    ]
    with tempfile.TemporaryFile() as log:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=log, check=False)
        log.seek(0)
        diagnostics = log.read().decode(errors="replace")
    frame_size = (width // 2) * (height // 4)
    field_timestamps = re.findall(r"\[showinfo@fields [^\]]+\]\s+n:\s*\d+\s+pts:\s*(-?\d+)", diagnostics)
    pts = np.array(field_timestamps, dtype=np.int64)
    order = re.findall(r"\[showinfo@pictures [^\]]+\]\s+n:[^\n]+?\bi:(\w)\b", diagnostics)
    if (result.returncode or len(result.stdout) != frame_size * len(pts) or len(order) * 2 != len(pts)
            or set(order) != {"T"}
            or not re.search(r"config in time_base: 1/180000, frame_rate: 60000/1001\b", diagnostics)):
        raise ValueError("expected a decodable 59.94-field/s NTSC MPEG-2 segment: "
                         f"decoded {len(pts)} fields, picture field order {sorted(set(order))}")
    frames = np.frombuffer(result.stdout, dtype=np.uint8).reshape(-1, height // 4, width // 2)
    return frames, pts


def field_deltas(frames):
    # The two fields have different line lattices. Blur both equally and move their samples
    # toward the shared midpoint by 1/8 of a row after the additional vertical downsample.
    frames = frames.astype(np.float32)
    smooth_x = (frames[:, :, :-2] + 2 * frames[:, :, 1:-1] + frames[:, :, 2:]) / 4
    smooth = (smooth_x[:, :-2] + 2 * smooth_x[:, 1:-1] + smooth_x[:, 2:]) / 4
    aligned = smooth[:, 1:-1].copy()
    aligned[::2] = .875 * aligned[::2] + .125 * smooth[::2, 2:]
    aligned[1::2] = .875 * aligned[1::2] + .125 * smooth[1::2, :-2]
    return np.abs(aligned[1:] - aligned[:-1]).mean(axis=(1, 2))


def repeat_runs(pts, delta, trim, ratio, min_pairs):
    if len(pts) < max(2 * trim + 5, 2 * min_pairs + 3):
        raise ValueError("segment too short for the selected trim and minimum run")
    if np.any(np.diff(pts[trim:len(pts) - trim]) != FIELD_PTS):
        raise ValueError("field clock discontinuity in the untrimmed segment")
    runs = []
    last = -3
    for pair in range(max(1, trim), min(len(delta) - 1, len(delta) - trim)):
        neighbor_change = min(delta[pair - 1], delta[pair + 1])
        if neighbor_change < 1 or delta[pair] >= ratio * neighbor_change:
            continue
        if pair != last + 2:
            runs.append([])
        runs[-1].append(pair)
        last = pair
    return [
        {
            "first_field": run[0],
            "last_field": run[-1] + 1,
            "first_pts_seconds": round(int(pts[run[0]]) / 180000, 6),
            "last_pts_seconds": round(int(pts[run[-1] + 1]) / 180000, 6),
            "repeated_pairs": len(run),
            "field_order": "first-to-second" if run[0] % 2 == 0 else "second-to-first",
        }
        for run in runs if len(run) >= min_pairs
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mpeg_segment", type=Path, help="short local segment of the original MPEG-2")
    parser.add_argument("--crop", type=crop_argument, required=True, metavar="W:H:X:Y")
    parser.add_argument("--trim-fields", type=int, default=24)
    parser.add_argument("--ratio", type=float, default=.45)
    parser.add_argument("--min-pairs", type=int, default=8)
    args = parser.parse_args()
    if args.trim_fields < 0 or not 0 < args.ratio < 1 or args.min_pairs < 1:
        parser.error("trim must be nonnegative, ratio between 0 and 1, and minimum pairs positive")
    try:
        frames, pts = decode_fields(args.mpeg_segment, args.crop)
        runs = repeat_runs(pts, field_deltas(frames), args.trim_fields, args.ratio, args.min_pairs)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({"decoded_fields": len(pts), "candidate_repeat_runs": runs}, indent=2))


if __name__ == "__main__":
    main()
