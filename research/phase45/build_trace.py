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
    parser.add_argument("--sync-controller", action="store_true",
                        help="synchronize the Stage 1 type-76 spawn during playback")
    skew = parser.add_mutually_exclusive_group()
    skew.add_argument("--force-record-retries", type=int, choices=range(1, 11), metavar="COUNT",
                      help="test early playback by delaying the recorded spawn")
    skew.add_argument("--withhold-playback-load", action="store_true",
                      help="test late playback by delaying native asset requests")
    parser.add_argument("--late-trace", action="store_true",
                        help="trace Noir Stage 1 graze, damage and RNG at updates 1000–1127")
    parser.add_argument("--bl-rom", type=Path)
    args = parser.parse_args()
    if args.symbols.exists() or args.output.exists():
        parser.error("choose new output paths")
    if args.delay_controller and not args.controller_trace:
        parser.error("--delay-controller requires --controller-trace")
    if args.sync_controller and (not args.controller_trace or args.delay_controller):
        parser.error("--sync-controller requires --controller-trace and conflicts with --delay-controller")
    if (args.force_record_retries or args.withhold_playback_load) and not args.sync_controller:
        parser.error("asset timing test options require --sync-controller")
    if args.late_trace and not args.sync_controller:
        parser.error("--late-trace requires --sync-controller")
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
    if args.sync_controller:
        profile["defines"].append("RP_CONTROLLER_SYNC")
    if args.force_record_retries:
        profile["defines"].append(f"RP_CONTROLLER_RECORD_RETRIES={args.force_record_retries}u")
    if args.withhold_playback_load:
        profile["defines"].append("RP_CONTROLLER_WITHHOLD_LOAD")
    if args.delay_controller:
        profile["defines"].append("RP_CONTROLLER_ONE_UPDATE")
    if args.late_trace:
        profile["defines"].append("RP_LATE_TRACE")
        profile["sources"] += ["replay_events.c", "replay_events_entry.S"]
        profile["stubs"] = [*profile["stubs"], ("replay_late_finish_entry", 0x00115620, "replay_late_end")]
        profile["sym_patches"] += [
            (0x00111050, 0x0C0580C4, "jal", "replay_late_rng_entry"),
            (0x0012E64C, 0x0C045588, "jal", "replay_late_finish_entry"),
            *((site, 0x0C04DCAC, "jal", "replay_late_retail_graze_entry")
              for site in (0x0012A92C, 0x0012ABD8)),
            *((site, 0x0C049E2C, "jal", "replay_late_damage_entry")
              for site in (0x0012AC04, 0x0012B254, 0x0012B578, 0x0012B8F4)),
        ]
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
