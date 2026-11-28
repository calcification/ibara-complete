#!/usr/bin/env python3
"""Build a local Noir trace disc with the release recorder and REPLAY menu."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import build_black_label_iso as disc
import build_ee_hooks as hooks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--symbols", type=Path, required=True)
    parser.add_argument("--bl-rom", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.symbols.exists():
        parser.error("choose new output paths")
    if not hooks.have_toolchain():
        parser.error("the MIPS cross toolchain is required")

    profile = hooks.HOOKS["kuro"]
    profile["sources"] = [*profile["sources"], str(Path(__file__).with_name("drift_probe.c").resolve())]
    profile["defines"] = [*profile["defines"], "RPL_TRACE", "RPL_DRIFT_PROBE"]
    profile["sym_patches"] = [
        # the probe's own FF27 gate replaces the release loader gate there
        *[x for x in profile["sym_patches"] if x[0] != 0x001EACAC],
        (0x001EACAC, 0x00114820, "word", "drift_gate"),
        (0x00115600, 0x0C058CD4, "jal", "drift_create"),
        (0x00163370, 0x0C04D75C, "jal", "drift_resources"),
        (0x00163398, 0x0C04B4A0, "jal", "drift_slots"),
        (0x00111050, 0x0C0580C4, "jal", "drift_rng_entry"),
    ]
    status = disc.main([str(args.source), "--output", str(args.output), "--bl-rom", str(args.bl_rom)])
    if status == 0:
        built, _ = hooks._load_hook("kuro")
        args.symbols.write_text(json.dumps(built["syms"], indent=2) + "\n")
    return status


if __name__ == "__main__":
    sys.exit(main())
