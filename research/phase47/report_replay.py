#!/usr/bin/env python3
"""Compare the release recorder's optional RPL_TRACE checkpoints."""
import argparse
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from p2s_tools import load_ee

HEADER = 0x01700000
RECORD = 0x01EA0000
PLAYBACK = 0x01EB0000
CHECKPOINT = struct.Struct("<4I")


def checkpoints(memory, base, count):
    return [CHECKPOINT.unpack_from(memory, base + i * CHECKPOINT.size) for i in range(count)]


def scene_changes(samples):
    changes = []
    for update, _, _, tick in samples:
        scene = tick >> 24
        if not changes or changes[-1]["scene"] != scene:
            changes.append(dict(update=update, scene=scene))
    return changes


def compare(record, playback, symbols):
    magic, checksum, version, head_size, size, updates = struct.unpack_from("<6I", record, HEADER)
    if magic != 0x42464249 or not updates or version not in (2, 3):
        raise ValueError("expected a complete format 2 or 3 replay")
    if playback[HEADER:HEADER + head_size + size] != record[HEADER:HEADER + head_size + size]:
        raise ValueError("recording and playback contain different replay files")
    played, end_flags, errors = struct.unpack_from("<3I", playback, symbols["rpl_stat"])
    if played != updates:
        raise ValueError(f"incomplete playback ({played} of {updates} updates)")
    count = min((updates + 29) // 30, 1000)
    before = checkpoints(record, RECORD, count)
    after = checkpoints(playback, PLAYBACK, count)
    if any(x[0] != i * 30 or y[0] != i * 30 for i, (x, y) in enumerate(zip(before, after))):
        raise ValueError("expected complete RPL_TRACE checkpoints")
    mismatches = [(x, y) for x, y in zip(before, after) if x != y]
    first = mismatches[0] if mismatches else None
    return dict(format=version, updates=updates, checksum=f"{checksum:08x}",
                target_cursor=struct.unpack_from("<I", record, HEADER + head_size - 8)[0] if version == 3 else None,
                compared=count, mismatches=len(mismatches), first_checkpoint=first,
                record_scenes=scene_changes(before), playback_scenes=scene_changes(after),
                end_mismatch=[name for i, name in enumerate(("score", "rng", "scene_tick")) if end_flags & 1 << i],
                stream_errors=errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    parser.add_argument("playback", type=Path)
    parser.add_argument("symbols", type=Path)
    args = parser.parse_args()
    try:
        symbols = json.loads(args.symbols.read_text())
        report = compare(load_ee(args.record), load_ee(args.playback), symbols)
    except (ValueError, KeyError, struct.error) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2))
    return int(bool(report["mismatches"] or report["end_mismatch"] or report["stream_errors"]))


if __name__ == "__main__":
    sys.exit(main())
