#!/usr/bin/env python3
"""Build the retail Arcade slowdown probe or export its hardware hook."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import build_ee_hooks as hooks
import build_pnach as pnach

PROFILE = {
    "test_id": "S01",
    "title": "Arcade slowdown gate probe",
    "description": "Cold boot with this profile alone. The probe starts disabled. See Phase 22.",
    "sources": ["arcade_slowdown.c"],
    "stubs": [],
    "sites": [],
    "jumps": [
        (0x0012E1E4, 0x144000F9, "arcade_slowdown_gate"),
        (0x0012E47C, 0x14400022, "arcade_slowdown_rank_gate"),
    ],
}
CAPTURE_BASE = 0x000D0000


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("retail", type=Path, help="clean SLPM_663.01 boot ELF or its original ISO")
    parser.add_argument("--output", type=Path, required=True, help="PCSX2 cheats folder or hardware JSON path")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--capture", action="store_true", help="add the research workload recorder")
    mode.add_argument("--measure-cycles", action="store_true", help="record workload and EE phase timing")
    mode.add_argument("--export-hardware", action="store_true", help="export the controller-triggered hook")
    args = parser.parse_args()

    if not hooks.have_toolchain():
        parser.error("the MIPS n32 cross toolchain is required")
    retail = pnach.load_elf(args.retail)
    profile = dict(PROFILE)
    capture = args.capture or args.measure_cycles
    if capture:
        profile.update(title="Arcade slowdown workload recorder", defines=["SLOWDOWN_CAPTURE"])
    if args.measure_cycles:
        profile["title"] = "Arcade slowdown EE cycle recorder"
        profile["defines"].append("SLOWDOWN_CYCLES")
        profile["sites"] = [
            (0x0012E5CC, 0x0C04E334, "arcade_slowdown_sim_start"),
            (0x0012E1EC, 0x0C045B08, "arcade_slowdown_draw_start"),
            (0x0012E464, 0x0C0445F4, "arcade_slowdown_submit"),
        ]
    if args.export_hardware:
        profile.update(defines=["SLOWDOWN_HARDWARE"])
    hooks.HOOKS["arcade_slowdown"] = profile
    hooks.LEAF_SOURCES.add("arcade_slowdown.c")
    with tempfile.TemporaryDirectory() as work:
        base = hooks.BAKE_BASE if args.export_hardware else hooks.CAVE_BASE
        end_limit = hooks.BAKE_END if args.export_hardware else CAPTURE_BASE if capture else hooks.CAVE_END
        built = hooks.build_hook("arcade_slowdown", Path(work), base=base, end_limit=end_limit)
    hooks.verify_sites(retail, built)
    if built["syms"]["arcade_slowdown"] != base:
        raise RuntimeError("unexpected location for the probe control block")
    if args.export_hardware:
        spec = hooks.export_bake(built)
        with args.output.open("x", encoding="utf-8") as output:
            print(json.dumps(spec, separators=(",", ":")), file=output)
        print(f"{args.output} ({built['size']} bytes of injected code and data)")
        return
    text = pnach.HEADER + "\n" + hooks.pnach_group(profile, built)
    pnach.check_pnach(text, min_addr=hooks.CAVE_BASE)
    args.output.mkdir(parents=True, exist_ok=True)
    path = args.output / pnach.NAME
    with path.open("x", encoding="utf-8") as output:
        output.write(text)
    print(f"{path} ({built['size']} bytes of injected code and data)")
    print(f"Probe control word: {built['syms']['arcade_slowdown'] + 4:08X}")
    if capture:
        print(f"Capture data: {CAPTURE_BASE:08X}")


if __name__ == "__main__":
    main()
