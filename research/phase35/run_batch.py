#!/usr/bin/env python3
"""Replay the same Stage 6 checkpoint with one new seed per PCSX2 trial."""
import argparse
import json
from pathlib import Path
import struct
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / part) for part in ("scripts", "research/phase30", "research/phase31")]
from p2s_tools import load_ee
from pcsx2_pine import Pine
from report_contacts import read_ps2
from report_roses import core_timing
from run_trial import CONTROL, MAGIC, STAGE, TICK, wait_for

CORE = 0x01F60000
RESTORING = 0xFFFFFFFF


def save_version(path):
    try:
        return path.stat().st_mtime_ns
    except FileNotFoundError:
        return None


def wait_for_save(path, previous):
    def ready():
        current = save_version(path)
        return current is not None and current != previous and zipfile.is_zipfile(path)

    wait_for(ready, 30, f"PCSX2 did not write a complete save to {path}")


def rose_sample_hp(pine):
    count = pine.read(CORE)
    if not 0 < count <= 8000 or pine.read(TICK) < 15000:
        return None
    for index in range(count - 1, max(-1, count - 9), -1):
        address = CORE + 16 + index * 24
        if pine.read(address + 8) == 2:
            return pine.read(address + 6, 16)
    return None


def summarize(path, seed):
    ram = load_ee(path)
    magic, mode, attempts, calls, misses, requested, applied, seed_tick, burst_frames = struct.unpack_from(
        "<9I", ram, CONTROL
    )
    if (magic, mode, requested, applied, seed_tick) != (MAGIC, 3, seed, seed, 10000):
        raise ValueError(f"{path}: seed or mode evidence is missing")
    if not attempts or not burst_frames or attempts != calls or misses:
        raise ValueError(f"{path}: incomplete rose barrage counters")
    cores, events = read_ps2(path)
    _, _, first = core_timing(cores, 0)
    start, stop, rose = core_timing(cores, 2)
    if first is None or rose is None:
        raise ValueError(f"{path}: both cores must reach zero")
    around = [event for event in events if start - 3 <= event.tick <= stop]
    core = [event for event in around if event.kind == 74 and event.subtype == 2]
    hits = [event for event in core if event.hp_loss]
    hp_lost = sum(event.hp_loss for event in hits)
    if hp_lost != 431:
        raise ValueError(f"{path}: expected 431 rose-core HP, traced {hp_lost}")
    roses, = struct.unpack_from("<I", ram, 0x01F5C000 + 12 * 79)
    return dict(seed=seed, first_core=first, rose_core=rose, rose_attempts=attempts,
                burst_frames=burst_frames, roses=roses, barrage_calls=calls,
                core_contacts=len(core), rose_contacts=sum(event.kind == 79 for event in around),
                long_gaps=sum(b.tick - a.tick > 12 for a, b in zip(hits, hits[1:])))


def run_batch(pine, checkpoint, output, directory, seeds, check_slot, save_slot):
    if check_slot == save_slot:
        raise ValueError("checkpoint and output slots must differ")
    ram = load_ee(checkpoint)
    marker, mode, attempts, _, _, request, applied, seeded_tick = struct.unpack_from("<8I", ram, CONTROL)
    tick, = struct.unpack_from("<I", ram, TICK)
    if (marker, mode, attempts, request, applied, seeded_tick) != (MAGIC, 3, 0, 0, 0, 0) \
            or ram[STAGE] != 7 or not 8500 <= tick < 9800:
        raise ValueError("use a mode-3 batch checkpoint made before Stage 6 tick 9800")

    directory.mkdir(parents=True, exist_ok=True)
    for seed in seeds:
        result = directory / f"{seed}.json"
        if result.exists():
            raise ValueError(f"choose a fresh output for seed {seed}")
        pine.write(CONTROL + 20, RESTORING)
        pine.load_state(check_slot)
        wait_for(lambda: pine.read(CONTROL + 20) == 0 and pine.read(STAGE, 8) == 7
                 and tick <= pine.read(TICK) < 10000, 20, "pre-seed checkpoint did not restore")
        pine.write(CONTROL + 20, seed)
        wait_for(lambda: pine.read(CONTROL + 24) == seed and pine.read(CONTROL + 28) == 10000,
                 40, "seed did not apply at tick 10000")
        print(f"Seed {seed} applied", flush=True)
        seen_positive = False

        def finished():
            nonlocal seen_positive
            hp = rose_sample_hp(pine)
            if hp is not None and hp > 0:
                seen_positive = True
            return ((seen_positive and hp == 0) or pine.read(TICK) >= 25000 or pine.read(STAGE, 8) != 7)

        wait_for(finished, 240, "rose core did not finish")
        previous = save_version(output)
        pine.save_state(save_slot)
        wait_for_save(output, previous)
        trial = summarize(output, seed)
        temporary = result.with_suffix(".partial")
        temporary.write_text(json.dumps(trial) + "\n")
        temporary.replace(result)
        print(json.dumps(trial), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("output_slot_file", type=Path)
    parser.add_argument("trial_directory", type=Path)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(5, 15)))
    parser.add_argument("--checkpoint-slot", type=int, default=7, choices=range(1, 11))
    parser.add_argument("--save-slot", type=int, default=8, choices=range(1, 11))
    parser.add_argument("--pine-slot", type=int, default=28011)
    args = parser.parse_args()
    if any(not 0 < seed < RESTORING for seed in args.seeds) or len(set(args.seeds)) != len(args.seeds):
        parser.error("provide distinct nonzero 32-bit seeds below 0xffffffff")
    if args.checkpoint.resolve() == args.output_slot_file.resolve():
        parser.error("checkpoint and output files must differ")
    pine = Pine(args.pine_slot)
    try:
        run_batch(pine, args.checkpoint, args.output_slot_file, args.trial_directory,
                  args.seeds, args.checkpoint_slot, args.save_slot)
    finally:
        pine.close()


if __name__ == "__main__":
    main()
