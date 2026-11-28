#!/usr/bin/env python3
"""Build the Phase 44 replay fixture without updating the committed profiles."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import build_black_label_iso as disc
import build_ee_hooks as hooks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--symbols", type=Path, required=True)
    parser.add_argument("--controller-trace", action="store_true")
    parser.add_argument("--delay-controller", action="store_true",
                        help="positive control: force one extra resource-check retry on playback")
    parser.add_argument("--bl-rom", type=Path)
    args = parser.parse_args()
    if args.symbols.exists() or args.output.exists():
        parser.error("choose new output paths")
    if args.delay_controller and not args.controller_trace:
        parser.error("--delay-controller requires --controller-trace")
    if not hooks.have_toolchain():
        parser.error("the MIPS cross toolchain is required for this test build")
    profile = hooks.HOOKS["kuro"]
    profile["sources"] = [*profile["sources"], "replay.c"]
    profile["defines"] = [*profile["defines"], "REPLAY_BUILD", "RP_FIRST_MODE=2u", "RP_SNAP_AT=400u"]
    profile["sym_patches"] = [
        *profile["sym_patches"],
        (0x00112B1C, 0x0C043774, "jal", "replay_pad_entry"),
        (0x00112B28, 0x0C043774, "jal", "replay_pad_entry"),
    ]
    if args.controller_trace:
        profile["defines"].append("RP_CONTROLLER_TRACE")
        profile["sym_patches"] += [
            (0x00115600, 0x0C058CD4, "jal", "replay_controller_create"),
            (0x00163370, 0x0C04D75C, "jal", "replay_controller_resources"),
            (0x00163398, 0x0C04B4A0, "jal", "replay_controller_slots"),
        ]
    if args.delay_controller:
        profile["defines"].append("RP_CONTROLLER_ONE_UPDATE")
    with tempfile.TemporaryDirectory() as tmp:
        built = hooks.build_hook("kuro", Path(tmp), hooks.BAKE_BASE, hooks.BAKE_END)
    argv = [str(args.source), "--output", str(args.output)]
    if args.bl_rom:
        argv += ["--bl-rom", str(args.bl_rom)]
    status = disc.main(argv)
    if status == 0:
        args.symbols.write_text(json.dumps(built["syms"], indent=2) + "\n")
    return status


if __name__ == "__main__":
    sys.exit(main())
