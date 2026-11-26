#!/usr/bin/env python3
"""Replay a PCSX2 Stage 2 pod census from one PINE checkpoint."""
import argparse
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from pcsx2_pine import Pine
from p2s_tools import load_ee

sys.path.insert(0, str(ROOT / "research" / "phase34"))
from ps2_trial import save_version, wait_for_save

BASE, MAGIC = 0x01F5E000, 0x31444F50
STAGE, TICK = 0x00338E9C, 0x00338EA0
WEAPONS = {3: 1, 4: 1, 6: 5}
TRACE_BASE = 0x01F80000
TRACE_ROW = struct.Struct("<48B9H")


def wait_for(test, timeout, message):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if test():
            return
        time.sleep(0.025)
    raise RuntimeError(message)


def run(pine, checkpoint, directory, check_slot, weapons=WEAPONS, trace_save=None):
    ram = load_ee(checkpoint)
    marker, _, _, _, _, exposure = struct.unpack_from("<6I", ram, BASE)
    tick, = struct.unpack_from("<I", ram, TICK)
    if marker != MAGIC or exposure or ram[STAGE] != 3 or not 700 <= tick < 1100:
        raise ValueError("expected an unarmed Stage 2 POD TEST checkpoint near tick 900")
    directory.mkdir(parents=True, exist_ok=True)
    for weapon in weapons:
        volley_size = WEAPONS[weapon]
        for seed in range(1, 4):
            dest = directory / f"{weapon}-{seed}.json"
            trace = dest.with_suffix(".trace")
            if dest.exists() and (trace_save is None or trace.exists()):
                continue
            pine.write(BASE + 8, 0xFFFFFFFF)
            pine.load_state(check_slot)
            wait_for(lambda: pine.read(BASE + 8) == 0 and pine.read(STAGE, 8) == 3
                     and tick <= pine.read(TICK) < 1200, 20, "checkpoint did not restore")
            pine.write(BASE + 4, weapon)
            pine.write(BASE + 8, seed)
            wait_for(lambda: pine.read(TICK) >= 3502, 120, "pod exposure did not finish")
            result = [pine.read(BASE + i * 4) for i in range(14)]
            _, _, _, applied_weapon, applied_seed, frames, attempts, successful, sampled, occupied, bad, x, y, ship = result
            if (applied_weapon, applied_seed, frames, bad, ship) != (weapon, seed, 1000, 0, 0):
                raise ValueError(f"weapon {weapon}, seed {seed}: invalid exposure {result}")
            allocations = successful * volley_size
            if not 0 < sampled <= allocations or attempts < successful:
                raise ValueError(f"weapon {weapon}, seed {seed}: inconsistent allocation counters {result}")
            result = dict(weapon=weapon, seed=seed, frames=frames, attempts=attempts,
                          allocations=allocations, sampled=sampled, occupied=occupied,
                          x=x >> 16, y=y >> 16)
            if trace_save is not None:
                previous = save_version(trace_save)
                pine.save_state(8)
                wait_for_save(trace_save, previous)
                memory = load_ee(trace_save)
                if struct.unpack_from("<14I", memory, BASE)[:11] != (
                        MAGIC, weapon, seed, weapon, seed, frames, attempts, successful, sampled, occupied, bad):
                    raise ValueError("the saved trace did not match the completed trial")
                data = memory[TRACE_BASE:TRACE_BASE + frames * TRACE_ROW.size]
                projectile = {3: 5, 4: 8, 6: 3}[weapon]
                if sum(
                        row[:48].count(projectile) for row in TRACE_ROW.iter_unpack(data)) != occupied:
                    raise ValueError("trace occupancy did not match the allocation census")
                partial = trace.with_suffix(".trace-partial")
                partial.write_bytes(data)
                partial.replace(trace)
            temporary = dest.with_suffix(".partial")
            temporary.write_text(json.dumps(result) + "\n")
            temporary.replace(dest)
            print(json.dumps(result), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--slot", type=int, default=7, choices=range(1, 11))
    parser.add_argument("--pine-slot", type=int, default=28011)
    parser.add_argument("--weapon", type=int, choices=WEAPONS, action="append")
    parser.add_argument("--trace-save", type=Path, help="slot 8 output from a BL_POD_AUDIT_LIFETIME build")
    args = parser.parse_args()
    if args.trace_save and (args.slot == 8 or args.checkpoint.resolve() == args.trace_save.resolve()):
        parser.error("slot 8 must be separate from the checkpoint when saving traces")
    pine = Pine(args.pine_slot)
    try:
        run(pine, args.checkpoint, args.out, args.slot, args.weapon or WEAPONS, args.trace_save)
    finally:
        pine.close()


if __name__ == "__main__":
    main()
