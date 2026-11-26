#!/usr/bin/env python3
"""Capture Stage 2 pod headings from the PCSX2 POD AIM diagnostic."""
import argparse
import csv
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "research" / "phase36"))
from p2s_tools import load_ee
from pcsx2_pine import Pine
from ps2_pods import BASE, MAGIC, STAGE, TICK, wait_for
sys.path.insert(0, str(ROOT / "research" / "phase34"))
from ps2_trial import save_version, wait_for_save

CONTROL = BASE + 0x100
FRAMES = 800
FIRST = 2400
ROW = struct.Struct("<ii10H")


def run(pine, checkpoint, savefile, output, check_slot=7, save_slot=8):
    memory = load_ee(checkpoint)
    tick, = struct.unpack_from("<I", memory, TICK)
    if (struct.unpack_from("<I", memory, BASE)[0] != MAGIC or memory[STAGE] != 3
            or not 700 <= tick < 1100):
        raise ValueError("expected an unarmed POD AIM Stage 2 checkpoint near tick 900")
    output.mkdir(parents=True, exist_ok=True)
    for control in range(4):
        name = ("stock-live", "stock-empty", "formation-live", "formation-empty")[control]
        result = output / f"ps2-{name}.csv"
        pine.write(BASE + 8, 0xFFFFFFFF)
        pine.load_state(check_slot)
        wait_for(lambda: pine.read(BASE + 8) == 0 and pine.read(STAGE, 8) == 3
                 and tick <= pine.read(TICK) < 1200, 20, "checkpoint did not restore")
        pine.write(BASE + 4, 3)
        pine.write(BASE + 8, 1)
        pine.write(CONTROL, control)
        wait_for(lambda: pine.read(TICK) >= FIRST + FRAMES, 150, "trace did not reach its endpoint")
        old = save_version(savefile)
        pine.save_state(save_slot)
        wait_for_save(savefile, old)
        ram = load_ee(savefile)
        if struct.unpack_from("<2I", ram, BASE + 12) != (3, 1):
            raise ValueError("the trace did not apply homing and seed 1")
        with result.with_suffix(".partial").open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(("tick", "mask", "x", "y", "pod", "angle", "desired", "target"))
            for frame in range(FRAMES):
                x, y, held, *pods = ROW.unpack_from(ram, CONTROL + 4 + frame * ROW.size)
                if not held & 16:
                    raise ValueError(f"missing shot input in trace at {frame}")
                for pod in range(3):
                    writer.writerow((frame, held & 15, x, y, pod, pods[pod],
                                     pods[3 + pod], pods[6 + pod]))
        result.with_suffix(".partial").replace(result)
        print(result, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path, help="existing slot 7 checkpoint")
    parser.add_argument("savefile", type=Path, help="slot 8 state written by PCSX2")
    parser.add_argument("output", type=Path)
    parser.add_argument("--pine-slot", type=int, default=28011)
    args = parser.parse_args()
    if args.checkpoint.resolve() == args.savefile.resolve():
        parser.error("checkpoint and savefile must occupy separate slots")
    pine = Pine(args.pine_slot)
    try:
        run(pine, args.checkpoint, args.savefile, args.output)
    finally:
        pine.close()


if __name__ == "__main__":
    main()
