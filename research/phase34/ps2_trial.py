#!/usr/bin/env python3
"""Run one PCSX2 damage trial from a local pre-seed checkpoint."""
from pathlib import Path
import argparse
import struct
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from p2s_tools import _read_member, load_ee
from pcsx2_pine import Pine

BASE = 0x01F60000
MAGIC = 0x31444850
STAGE = 0x00338E9C
TICK = 0x00338EA0
SEED_TICK = 2000
HEADER = struct.Struct("<8I")
SAMPLE = struct.Struct("<IIHHBBBB")
RESTORING = 0xFFFFFFFF
LOADOUT = BASE - 16
LOADOUT_STATE = struct.Struct("<4I")


def wait_for(predicate, timeout, why):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.025)
    raise RuntimeError(why)


def parse_loadout(value):
    try:
        fields = bytes(int(field) for field in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected four comma-separated byte values") from exc
    if len(fields) != 4 or not all(fields):
        raise argparse.ArgumentTypeError("expected three equipped pod kinds and the selected weapon")
    return int.from_bytes(fields, "little")


def arm_loadout(pine, packed):
    pine.write(LOADOUT, packed)
    wait_for(lambda: pine.read(LOADOUT + 4) == packed and pine.read(LOADOUT + 8) >= 1,
             10, "the matched-pod diagnostic did not equip the requested loadout")


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


def seed_checkpoint(source, destination, stage, seed, boss):
    """Materialize a copy that sets the LCG at this exact, pre-boss checkpoint."""
    if source.resolve() == destination.resolve():
        raise ValueError("use a separate seeded savestate slot")
    temporary = destination.with_suffix(".partial")
    with zipfile.ZipFile(source) as original:
        ee = bytearray(load_ee(source))
        magic, _, _, _, count, dropped, recorded_stage, _ = HEADER.unpack_from(ee, BASE)
        tick, = struct.unpack_from("<I", ee, TICK)
        if magic != MAGIC or recorded_stage != stage or count or dropped or ee[STAGE] != stage:
            raise ValueError("checkpoint must be in the intended stage before any boss samples")
        HEADER.pack_into(ee, BASE, MAGIC, seed, seed, tick, 0, 0, stage, boss)
        struct.pack_into("<I", ee, 0x00337D08, seed)
        try:
            with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=2) as seeded:
                for member in original.infolist():
                    seeded.writestr(member.filename, ee if member.filename == "eeMemory.bin" else
                                    _read_member(source, member))
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    return tick


def capture(pine, stage, seed, boss, check_slot, save_slot, max_tick, gauge=False, seeded_tick=None,
            loadout=None):
    pine.write(BASE + 4, RESTORING)
    pine.load_state(check_slot)
    if seeded_tick is None:
        wait_for(lambda: pine.read(BASE) == MAGIC and pine.read(BASE + 4) == 0
                 and pine.read(BASE + 24) == stage and pine.read(TICK) < SEED_TICK,
                 20, "the pre-seed checkpoint did not restore")
        pine.write(BASE + 28, boss)
        if loadout is not None:
            wait_for(lambda: pine.read(TICK) >= 1200, 30, "takeoff hold did not finish")
            arm_loadout(pine, loadout)
        pine.write(BASE + 4, seed)
        seeded_tick = SEED_TICK
    wait_for(lambda: pine.read(BASE) == MAGIC and pine.read(BASE + 4) == seed
             and pine.read(BASE + 8) == seed and pine.read(BASE + 12) == seeded_tick
             and pine.read(BASE + 24) == stage,
             60, "the checkpoint did not apply the seed at the fixed tick")
    seen_hp = False

    def done():
        nonlocal seen_hp
        if pine.read(STAGE, 8) != stage or pine.read(TICK) >= max_tick:
            return True
        count = pine.read(BASE + 16)
        if not boss or not count:
            return False
        address = BASE + HEADER.size + SAMPLE.size * (count - 1)
        hp = pine.read(address + (4 if gauge else 8), 32 if gauge else 16)
        seen_hp = seen_hp or hp > 0
        return seen_hp and hp == 0

    wait_for(done, 480, "boss capture did not reach its endpoint")
    pine.save_state(save_slot)


def export_samples(path, stage, seed, out, gauge=False, seed_tick=SEED_TICK, loadout=None):
    ram = load_ee(path)
    magic, requested, applied, tick, count, dropped, recorded_stage, boss = HEADER.unpack_from(ram, BASE)
    if (magic, requested, applied, tick, recorded_stage) != (MAGIC, seed, seed, seed_tick, stage):
        raise ValueError(f"{path}: stage or seed metadata does not match the trial")
    if dropped or count > 8000:
        raise ValueError(f"{path}: incomplete capture ({count} records, {dropped} dropped)")
    rows = [f"# stage {stage - 1} seed {seed} boss {boss} seed_tick {tick}"]
    if loadout is not None:
        requested_loadout, equipped, checked, mismatches = LOADOUT_STATE.unpack_from(ram, LOADOUT)
        if requested_loadout != loadout or equipped != loadout or not checked or mismatches:
            raise ValueError(f"{path}: pod audit failed ({equipped:08x}, {checked} checked, "
                             f"{mismatches} mismatched frames)")
        fields = " ".join(str(field) for field in loadout.to_bytes(4, "little"))
        rows.append(f"# loadout {fields} verified_frames {checked}")
    for index in range(count):
        frame, gauge_hp, part_hp, gauge_state, slot, kind, subtype, scene = SAMPLE.unpack_from(
            ram, BASE + HEADER.size + SAMPLE.size * index
        )
        if scene != stage:
            raise ValueError(f"{path}: sample crossed the stage boundary")
        hp = gauge_hp if gauge else part_hp
        rows.append(f"{frame} {slot} {hp} {subtype:08X} {kind} {part_hp} {gauge_hp} {gauge_state}")
    temporary = out.with_suffix(".partial")
    temporary.write_text("\n".join(rows) + "\n")
    temporary.replace(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=int, choices=range(1, 6), required=True)
    parser.add_argument("--seed", type=int, metavar="UINT32", required=True)
    parser.add_argument("--boss-type", type=int, required=True, help="0 logs candidate parts")
    parser.add_argument("--max-tick", type=int, default=19000)
    parser.add_argument("--source-checkpoint", type=Path, help="optional late pre-boss .p2s file")
    parser.add_argument("--seeded-file", type=Path, help="slot file to write when using --source-checkpoint")
    parser.add_argument("--save-file", type=Path, required=True, help="autosaved .p2s path for --save-slot")
    parser.add_argument("--loadout", type=parse_loadout, metavar="POD1,POD2,POD3,WEAPON",
                        help="require this loadout from the matched-pod diagnostic")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--checkpoint-slot", type=int, default=7, choices=range(1, 11))
    parser.add_argument("--save-slot", type=int, default=8, choices=range(1, 11))
    parser.add_argument("--pine-slot", type=int, default=28011)
    parser.add_argument("--gauge", action="store_true", help="use the native gauge instead of the part's HP")
    args = parser.parse_args()
    if not 0 < args.seed < RESTORING:
        parser.error("seed must be between 1 and 4294967294")
    if args.checkpoint_slot == args.save_slot:
        parser.error("checkpoint and output slots must differ")
    if bool(args.source_checkpoint) != bool(args.seeded_file):
        parser.error("--source-checkpoint and --seeded-file must be supplied together")
    if args.seeded_file and args.seeded_file.resolve() == args.save_file.resolve():
        parser.error("seeded checkpoint and output paths must differ")
    seeded_tick = None
    if args.source_checkpoint:
        if args.loadout is not None:
            requested, equipped, checked, mismatches = LOADOUT_STATE.unpack_from(
                load_ee(args.source_checkpoint), LOADOUT)
            if requested != args.loadout or equipped != args.loadout or not checked or mismatches:
                parser.error("equip the requested loadout before saving a late source checkpoint")
        seeded_tick = seed_checkpoint(args.source_checkpoint, args.seeded_file, args.stage + 1,
                                      args.seed, args.boss_type)
    old = save_version(args.save_file)
    pine = Pine(args.pine_slot)
    try:
        capture(pine, args.stage + 1, args.seed, args.boss_type, args.checkpoint_slot,
                args.save_slot, args.max_tick, args.gauge, seeded_tick, args.loadout)
        wait_for_save(args.save_file, old)
    finally:
        pine.close()
    export_samples(args.save_file, args.stage + 1, args.seed, args.out, args.gauge,
                   seeded_tick if seeded_tick is not None else SEED_TICK, args.loadout)


if __name__ == "__main__":
    main()
