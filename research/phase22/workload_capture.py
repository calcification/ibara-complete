#!/usr/bin/env python3
"""Arm or export the S01 workload recorder in PCSX2."""

import argparse
import csv
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from pcsx2_pine import Pine, READ32
from score_slowdown import read_trace


CAPTURE_SIGNATURE = 0x000C0018
CAPTURE_ENABLED = 0x000C001C
CAPTURE_COUNT = 0x000C0020
BOMB_START = 0x000C0024
BOMB_RELEASE = 0x000C0028
SHOT_TICKS = 0x000C002C
CADENCE_TICKS = 0x000C0030
CADENCE_MASK = 0x000C0034
MANUAL_ENABLE = 0x000C0004
CAPTURE_BASE = 0x000D0000
CAPTURE_LIMIT = 2048
TICK = 0x00338EA0
SCENE = 0x00338E9C
PRACTICE = 0x00338FA4
ROW = struct.Struct("<IIIii6H4B")
CYCLE_ROW = struct.Struct("<5I")
DRAW_PASS_ROW = struct.Struct("<12I")
CYCLE_BASE = CAPTURE_BASE + CAPTURE_LIMIT * ROW.size
HEADER = (
    "outer_loop", "gameplay_tick", "inverted_rank", "player_x_16_16", "player_y_16_16",
    "held_buttons", "released_buttons", "hostile_bullets", "active_enemies", "rose_pods",
    "active_items", "bombs", "holding", "scene", "flying_form",
)
CYCLE_HEADER = ("ee_sim_counts", "ee_draw_counts", "ee_submit_counts")
DRAW_PASS_HEADER = (
    "ee_draw_setup_counts", "ee_layers_counts", "ee_overlays_counts",
    "ee_setup_slots", "ee_layers_slots", "ee_overlays_slots", "ee_submit_slots",
)


def verify_probe(pine):
    signature = pine.read(CAPTURE_SIGNATURE)
    if signature not in (0x31544C53, 0x32544C53, 0x33544C53, 0x34544C53, 0x35544C53):
        raise ValueError("load the S01 workload or cycle recorder")
    return (signature >> 24) - ord("0")


def cadence_mask(ticks):
    updates = ticks[-1] - ticks[0]
    if not 0 < updates <= CAPTURE_LIMIT:
        raise ValueError("cadence must advance within the capture limit")
    mask = [0] * ((updates + 31) // 32)
    for before, after in zip(ticks, ticks[1:]):
        if before == after:
            word, bit = divmod(before - ticks[0], 32)
            if mask[word] & (1 << bit):
                raise ValueError("cadence supports at most one hold per gameplay update")
            mask[word] |= 1 << bit
    return updates, mask


def arm(pine, bomb_delay=None, charge_ticks=0, shot_ticks=0, cadence=None):
    version = verify_probe(pine)
    if shot_ticks < 0 or (shot_ticks and bomb_delay is None):
        raise ValueError("use a nonnegative shot duration and schedule a bomb when firing")
    if shot_ticks and version < 2:
        raise ValueError("rebuild the --capture profile to schedule shot input")
    if cadence is not None:
        if version < 3 or bomb_delay is None:
            raise ValueError("cadence playback needs the latest --capture profile and --bomb-delay")
        updates, mask = cadence_mask(cadence)
        if bomb_delay + charge_ticks + len(cadence) >= CAPTURE_LIMIT:
            raise ValueError("the charge and cadence exceed the capture window")
        if pine.read(MANUAL_ENABLE):
            raise ValueError("turn off forced half speed before arming cadence playback")
    start = release = 0
    if bomb_delay is not None:
        if bomb_delay < 1 or charge_ticks < 1:
            raise ValueError("bomb delay and charge duration must be positive")
        if bomb_delay + charge_ticks + shot_ticks >= CAPTURE_LIMIT // 2 - 1:
            raise ValueError("schedule the input within the capture window")
        if pine.status() != "paused" or pine.read(SCENE, 8) != 7 or not pine.read(PRACTICE):
            raise ValueError("pause PCSX2 in Arcade Practice Stage 6 to schedule a bomb")
        start = pine.read(TICK) + bomb_delay
        release = start + charge_ticks
    pine.write(CAPTURE_ENABLED, 0)
    pine.write(CAPTURE_COUNT, 0)
    pine.write(BOMB_START, start)
    pine.write(BOMB_RELEASE, release)
    if version >= 2:
        pine.write(SHOT_TICKS, shot_ticks)
    if version >= 3:
        pine.write(CADENCE_TICKS, 0)
        if cadence is not None:
            for index, word in enumerate(mask):
                pine.write(CADENCE_MASK + index * 4, word)
            pine.write(CADENCE_TICKS, updates)
    pine.write(CAPTURE_ENABLED, 1)


def read_sample_buffer(pine, base, layout, count):
    rows = []
    word = struct.Struct("<BI")
    for begin in range(0, count, 128):
        size = layout.size * min(128, count - begin)
        start = base + layout.size * begin
        body = b"".join(word.pack(READ32, addr) for addr in range(start, start + size, 4))
        pine.sock.sendall(struct.pack("<I", 4 + len(body)) + body)
        total, = struct.unpack("<I", pine._recv(4))
        reply = pine._recv(total - 4)
        if reply[0] != 0 or len(reply) != 1 + size:
            raise RuntimeError("unexpected PINE batch reply")
        rows.extend(layout.iter_unpack(reply[1:]))
    return rows


def read_rows(pine, *, cycles=False, draw_passes=False):
    version = verify_probe(pine)
    if draw_passes and version < 5:
        raise ValueError("draw-pass export requires the S01 profile built with --measure-draw-passes")
    if cycles and version < 4:
        raise ValueError("cycle export requires the S01 profile built with --measure-cycles")
    pine.write(CAPTURE_ENABLED, 0)
    count = pine.read(CAPTURE_COUNT)
    if count > CAPTURE_LIMIT:
        raise ValueError("invalid sample count")
    rows = read_sample_buffer(pine, CAPTURE_BASE, ROW, count)
    if not (cycles or draw_passes):
        return rows
    layout = DRAW_PASS_ROW if version >= 5 else CYCLE_ROW
    marks = read_sample_buffer(pine, CYCLE_BASE, layout, count)
    timed = []
    wrap = 0xFFFFFFFF
    for index, (row, mark) in enumerate(zip(rows, marks)):
        sim, draw, submit, end, complete = mark[:5]
        if not complete and index == count - 1:
            break  # Recording can be stopped while the last update is still being drawn.
        if complete != 1:
            raise RuntimeError(f"timing marks incomplete for sample {index}")
        sim_counts = 0 if row[12] else (draw - sim) & wrap
        sample = (*row, sim_counts, (submit - draw) & wrap, (end - submit) & wrap)
        if draw_passes:
            layers, overlays, setup_end, layer_end, overlay_end, final, initial = mark[5:]
            if not (0 <= initial <= setup_end <= layer_end <= overlay_end <= final <= 3000):
                raise RuntimeError(f"sprite-slot counter went out of order on sample {index}")
            sample += ((layers - draw) & wrap, (overlays - layers) & wrap, (submit - overlays) & wrap,
                       setup_end - initial, layer_end - setup_end, overlay_end - layer_end, final - overlay_end)
        timed.append(sample)
    return timed


def timing_window(path, start, ticks):
    if start < 0 or ticks < 1:
        raise ValueError("start tick must be nonnegative and the window must advance")
    rows = []
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        columns = ("outer_loop", "gameplay_tick", "holding", "scene")
        if not set(columns) <= set(reader.fieldnames or []):
            raise ValueError("expected S01 workload capture columns")
        for row in reader:
            try:
                outer, tick, holding, scene = (int(row[key]) for key in columns)
            except (ValueError, TypeError) as error:
                raise ValueError(f"{path}:{reader.line_num}: invalid timing sample") from error
            if holding not in (0, 1):
                raise ValueError(f"{path}:{reader.line_num}: holding must be zero or one")
            if not rows and tick != start:
                continue
            if rows:
                prev_outer, prev_tick, prev_holding, prev_scene = rows[-1]
                if outer != prev_outer + 1 or tick != prev_tick + 1 - prev_holding or scene != prev_scene:
                    raise ValueError("workload capture has a timing gap or scene change")
            rows.append((outer, tick, holding, scene))
            if tick == start + ticks:
                return [entry[1] for entry in rows]
    raise ValueError("workload capture does not contain the whole timing window")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slot", type=int, default=28011)
    subcommands = parser.add_subparsers(dest="command", required=True)
    start = subcommands.add_parser("arm", help="reset the capture and start recording")
    start.add_argument("--bomb-delay", type=int, help="gameplay ticks until the charge starts")
    start.add_argument("--charge-ticks", type=int, default=138)
    start.add_argument("--shot-ticks", type=int, default=0, help="hold shot through this many gameplay ticks after the bomb release")
    start.add_argument("--cadence", type=Path, help="single-window timing CSV to replay after bomb release")
    save = subcommands.add_parser("export", help="stop recording and write CSV")
    save.add_argument("csv", type=Path)
    format_flags = save.add_mutually_exclusive_group()
    format_flags.add_argument("--cycles", action="store_true", help="include timing from --measure-cycles")
    format_flags.add_argument("--draw-passes", action="store_true", help="include timing and sprite slots by draw pass")
    timing = subcommands.add_parser("timing", help="extract a timing window from a workload CSV")
    timing.add_argument("capture", type=Path)
    timing.add_argument("trace", type=Path)
    timing.add_argument("--window", required=True)
    timing.add_argument("--start-tick", required=True, type=int)
    timing.add_argument("--ticks", required=True, type=int)
    args = parser.parse_args()
    try:
        if args.command == "timing":
            ticks = timing_window(args.capture, args.start_tick, args.ticks)
            with args.trace.open("x", newline="", encoding="utf-8") as target:
                writer = csv.writer(target)
                writer.writerow(("window", "frame", "tick"))
                writer.writerows((args.window, frame, tick) for frame, tick in enumerate(ticks))
            return
        pine = Pine(args.slot)
        try:
            if args.command == "arm":
                cadence = None
                if args.cadence is not None:
                    windows = read_trace(args.cadence)
                    if len(windows) != 1:
                        raise ValueError("cadence requires a single timing window")
                    cadence = next(iter(windows.values()))
                arm(pine, args.bomb_delay, args.charge_ticks, args.shot_ticks, cadence)
            else:
                rows = read_rows(pine, cycles=args.cycles, draw_passes=args.draw_passes)
                columns = HEADER
                if args.cycles or args.draw_passes:
                    columns += CYCLE_HEADER
                if args.draw_passes:
                    columns += DRAW_PASS_HEADER
                with args.csv.open("x", newline="", encoding="utf-8") as target:
                    writer = csv.writer(target)
                    writer.writerow(columns)
                    writer.writerows(rows)
                print(f"Exported {len(rows)} samples to {args.csv}")
        finally:
            pine.close()
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
