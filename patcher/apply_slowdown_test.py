#!/usr/bin/env python3
"""Build the controller-triggered Arcade slowdown hardware test from an original Ibara ISO."""

import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "research" / "phase03"))
import build_ee_hooks as hooks
import ibara_complete_bootstrap as disc


def build(source, output):
    _, root, records, _, source_hash = disc.check_source(source)
    boot = next(rec for rec in records if rec["name"] == b"SLPM_663.01;1")
    spec = json.loads((hooks.PREBUILT / "arcade_slowdown_hw.json").read_text(encoding="utf-8"))
    with source.open("rb") as original:
        elf = disc.read_at(original, boot["lba"] * disc.SECTOR, boot["size"])
        payload = hooks.bake_elf(elf, hooks.import_bake(spec))
        offset = disc.NEW_FILE_LBA * disc.SECTOR
        reserved = (len(payload) + disc.SECTOR - 1) // disc.SECTOR * disc.SECTOR
        if offset + reserved > disc.NEXT_ORIGINAL_FILE_LBA * disc.SECTOR:
            raise ValueError("The test ELF exceeds the reserved disc space")
        if any(disc.read_at(original, offset, reserved)):
            raise ValueError("The reserved disc sectors are in use")
        root = bytearray(root)
        at = boot["offset"]
        root[at + 2:at + 18] = disc.pair32(disc.NEW_FILE_LBA) + disc.pair32(len(payload))
        root_offset = disc.ORIGINAL_ROOT_LBA * disc.SECTOR
        original.seek(0)
        target = output.open("x+b")
        try:
            with target:
                shutil.copyfileobj(original, target, 4 * 1024 * 1024)
                target.seek(root_offset)
                target.write(root)
                target.seek(offset)
                target.write(payload)
                if disc.read_at(target, root_offset, len(root)) != root:
                    raise ValueError("The output ISO directory failed verification")
                if disc.read_at(target, offset, len(payload)) != payload:
                    raise ValueError("The injected boot executable failed verification")
            if disc.digest_file(source) != source_hash:
                raise ValueError("The input ISO changed during the build")
        except BaseException:
            output.unlink(missing_ok=True)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="original Japanese Ibara ISO")
    parser.add_argument("--output", type=Path, required=True, help="new test ISO path")
    args = parser.parse_args()
    try:
        build(args.source, args.output)
    except (OSError, ValueError, AssertionError) as error:
        parser.error(str(error))
    print(f"Created {args.output}")


if __name__ == "__main__":
    main()
