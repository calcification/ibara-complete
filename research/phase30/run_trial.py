#!/usr/bin/env python3
"""Replay one Stage 6 PCSX2 probe trial from a pre-boss checkpoint."""
import argparse
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from p2s_tools import load_ee
from pcsx2_pine import Pine

CONTROL = 0x01F5E000
MAGIC = 0x31534F52
STAGE = 0x00338E9C
TICK = 0x00338EA0
RESTORING = 0x80000000


def wait_for(check, timeout, message):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.025)
    raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path, help="local pre-boss .p2s for the loaded probe disc")
    parser.add_argument("--checkpoint-slot", type=int, required=True, choices=range(1, 11))
    parser.add_argument("--save-slot", type=int, required=True, choices=range(1, 11),
                        help="use an empty slot in the dedicated test profile")
    parser.add_argument("--mode", type=int, required=True, choices=range(4))
    parser.add_argument("--pine-slot", type=int, default=28011)
    args = parser.parse_args()
    if args.checkpoint_slot == args.save_slot:
        parser.error("checkpoint and output slots must differ")

    ram = load_ee(args.checkpoint)
    marker, saved_mode, attempts = struct.unpack_from("<3I", ram, CONTROL)
    tick, = struct.unpack_from("<I", ram, TICK)
    if marker != MAGIC or saved_mode != 0 or attempts or ram[STAGE] != 7 or not 10000 <= tick < 11800:
        parser.error("checkpoint must come from the baseline probe shortly before the first Stage 6 core")

    pine = Pine(args.pine_slot)
    try:
        if pine.read(CONTROL) != MAGIC:
            raise RuntimeError("boot the logger disc and load its Stage 6 checkpoint first")
        # Distinguish the asynchronous restore from reads still returning the previous run.
        pine.write(CONTROL + 4, RESTORING)
        pine.load_state(args.checkpoint_slot)
        wait_for(lambda: pine.read(CONTROL + 4) == 0 and pine.read(CONTROL + 8) == 0
                 and pine.read(STAGE, 8) == 7 and tick <= pine.read(TICK) < 12000,
                 20, "PCSX2 did not restore the expected pre-boss state")
        pine.write(CONTROL + 4, args.mode)
        if pine.read(CONTROL + 4) != args.mode:
            raise RuntimeError("mode write did not survive the checkpoint restore")
        print(f"Mode {args.mode} active at native tick {pine.read(TICK)}", flush=True)
        wait_for(lambda: pine.read(STAGE, 8) != 7 or pine.read(TICK) >= 26000,
                 420, "Stage 6 trial timed out")
        if pine.read(CONTROL + 4) != args.mode:
            raise RuntimeError("mode changed during the trial")
        pine.save_state(args.save_slot)
        print(f"Requested save to slot {args.save_slot}")
    finally:
        pine.close()


if __name__ == "__main__":
    main()
