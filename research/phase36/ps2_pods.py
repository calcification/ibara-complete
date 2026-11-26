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

BASE, MAGIC = 0x01F5E000, 0x31444F50
STAGE, TICK = 0x00338E9C, 0x00338EA0
WEAPONS = {3: 1, 4: 1, 6: 5}


def wait_for(test, timeout, message):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if test():
            return
        time.sleep(0.025)
    raise RuntimeError(message)


def run(pine, checkpoint, directory, check_slot, weapons=WEAPONS):
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
            if dest.exists():
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
    args = parser.parse_args()
    pine = Pine(args.pine_slot)
    try:
        run(pine, args.checkpoint, args.out, args.slot, args.weapon or WEAPONS)
    finally:
        pine.close()


if __name__ == "__main__":
    main()
