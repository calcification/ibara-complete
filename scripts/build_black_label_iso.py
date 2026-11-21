#!/usr/bin/env python3
"""Build a testable Ibara disc image with a BLACK LABEL entry in Mode Select — one command.

    python3 scripts/build_black_label_iso.py 'Ibara (Japan).iso' --output 'Ibara Black Label test.iso'

What it does (nothing is downloaded; your ISO is only read):
1. checks your ISO is the exact Japanese retail disc (SLPM-66301, ELF SHA-256 263d3079..., CRC 420C7FAB);
2. bakes the BLACK LABEL executable: a copy of the retail executable with this project's Black Label code
   (ps2/hooks: XTC graze counter + HUD, weapon stock and change button, shot levels, rank rules, return to
   the launcher) and the same video profile as the launcher;
3. builds a separate ISO whose Mode Select has an extra row (default: KURO, third, after Arcade and Arrange)
   (research/phase04/build_menu_probe.py). Arcade, Arrange, Gallery, Option and Exit are the retail ones.

Requirements: Python 3.10+ and `pip install -r requirements-assets.txt` (Pillow, numpy). The MIPS cross
compiler is optional: without it the committed prebuilt hook image (ps2/prebuilt/bl_mode.json) is used.
Output is ~3.7 GB and contains game data: keep it local, never upload it.

Play: boot the new ISO (PCSX2 with cheats off, or your usual loader), Start at the title, then Down twice to
KURO (third row) and Circle (Circle confirms, Cross cancels; Cross = shot, Circle = bomb, Square = weapon change).
Inside, play Arcade as usual; EXIT in its Mode Select returns to the launcher. Report results with
tests/manual/RESULT_TEMPLATE.md.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "research" / "phase04"))
sys.path.insert(0, str(ROOT / "research" / "phase03"))

import build_ee_hooks  # noqa: E402
import build_pnach  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=Path, help="your clean 'Ibara (Japan).iso'")
    ap.add_argument("--output", type=Path, required=True, help="new ISO to create (must not exist)")
    ap.add_argument("--video-profile", default="auto",
                    help="auto (default: Yoko interlaced without filtering, Tate 240p), 240p_cave_beta (240p in every "
                         "mode; verified on a real PS2), 240p_halfpixel, 240p_core or retail")
    ap.add_argument("--label", default="KURO", help="menu label for the Black Label entry (short, ASCII)")
    ap.add_argument("--position", type=int, choices=(2, 5), default=2,
                    help="menu row of the entry: 2 = third, right after Arcade and Arrange (default); 5 = bottom")
    ap.add_argument("--keep-elf", type=Path, help="also save the baked BLACK LABEL executable here")
    args = ap.parse_args(argv)

    if args.output.exists():
        ap.error(f"{args.output} already exists; choose a new name")
    try:
        import build_menu_probe
    except ImportError as exc:
        ap.error(f"missing Python dependency ({exc}); run: pip install -r requirements-assets.txt")
    if args.video_profile not in build_menu_probe.VIDEO_PROFILES:
        ap.error(f"unknown video profile; choose from {sorted(build_menu_probe.VIDEO_PROFILES)}")

    print("1/3 checking the retail disc ...")
    retail = build_pnach.load_elf(args.source)  # exact SHA-256 and PCSX2 CRC, or it refuses
    print("    OK: SLPM-66301, CRC 420C7FAB")

    print("2/3 baking the BLACK LABEL executable ...")
    payload, origin = build_ee_hooks.bake_payload(retail, "bl_mode", args.video_profile)
    print(f"    {len(payload):,} bytes, hook code {origin}, video {args.video_profile}")
    print(f"    SHA-256 {hashlib.sha256(payload).hexdigest()}")

    print("3/3 building the launcher disc (this copies ~3.7 GB) ...")
    with tempfile.TemporaryDirectory() as tmp:
        elf = Path(tmp) / "KURO.ELF"
        elf.write_bytes(payload)
        if args.keep_elf:
            args.keep_elf.write_bytes(payload)
        crc, sha = build_menu_probe.build(args.source, args.output, elf, label=args.label,
                                          video_profile=args.video_profile, position=args.position,
                                          executable_hook=build_ee_hooks.frontend_video_hook(args.video_profile))
    print(f"\nCreated {args.output}")
    print(f"Launcher executable CRC {crc:08X}, SHA-256 {sha}")
    print(f"Boot it, press Start at the title, move to {args.label} (row {args.position + 1}), Circle. EXIT inside returns to the launcher.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (AssertionError, ValueError, OSError) as err:
        print("FAIL:", err, file=sys.stderr)
        sys.exit(1)
