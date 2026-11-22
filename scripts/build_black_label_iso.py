#!/usr/bin/env python3
"""Build a testable Ibara disc image with a BLACK LABEL entry in Mode Select — one command.

    python3 scripts/build_black_label_iso.py 'Ibara (Japan).iso' --output 'Ibara Black Label test.iso'

What it does (nothing is downloaded; your ISO is only read):
1. checks your ISO is the exact Japanese retail disc (SLPM-66301, ELF SHA-256 263d3079..., CRC 420C7FAB);
2. bakes this project's code into the game's executable (ps2/hooks/kuro.c "instant KURO": the Black Label code
   — XTC graze counter + HUD, weapon stock and change button, shot levels, rank and enemy rules — is switched on
   when KURO is chosen and off when you leave it, no reload; plus the video and menu options);
3. builds a separate ISO whose Mode Select has an extra row (default: KURO, third, after Arcade and Arrange)
   (research/phase04/build_menu_probe.py).

Requirements: Python 3.10+ and `pip install -r requirements-assets.txt` (Pillow, numpy). The MIPS cross
compiler is optional: without it the committed prebuilt hook image (ps2/prebuilt/kuro.json) is used.
Output is ~3.7 GB and contains game data: keep it local, never upload it.

Play: boot the new ISO (PCSX2 with cheats off, or your usual loader), Start at the title, then Down twice to
KURO (third row) and Circle (Circle confirms, Cross cancels; Cross = shot, Circle = bomb, Square = weapon change).
KURO opens ARCADE MODE's menu with Black Label rules; its EXIT returns to Mode Select. Report results with
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
    ap.add_argument("--video-profile", default=build_ee_hooks.FULL_FRAME_AUTO,
                    help="auto_full_frame (default: interlaced Yoko, 240 active lines in NTSC Tate), auto (224-line "
                         "Tate), 240p_full_frame, 240p_cave_beta, 240p_halfpixel, 240p_core or retail")
    ap.add_argument("--label", default="KURO", help="menu label for the Black Label entry (short, ASCII)")
    ap.add_argument("--position", type=int, choices=(2, 5), default=2,
                    help="menu row of the entry: 2 = third, right after Arcade and Arrange (default); 5 = bottom")
    ap.add_argument("--rank-gauge", choices=("arcade", "arrange"), default="arcade",
                    help="arcade (default): ARCADE MODE > CONFIG gets a RANK GAUGE ON/OFF row (starts ON) that shows "
                         "Arrange's RANK gauge in Arcade (launcher and KURO); arrange: retail behaviour, no row")
    ap.add_argument("--bl-rom", type=Path, help="your own ibarablk ROM (zip or ibarablk_u2): copies the Black Label RANK "
                    "bar's artwork into the disc (research/phase19); without it KURO shows Arrange's gauge")
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

    print("2/3 building the instant-KURO executable ...")
    hook = build_ee_hooks.frontend_video_hook(args.video_profile, rank_gauge=args.rank_gauge == "arcade",
                                              position=args.position)
    print("3/3 building the disc (this copies ~3.7 GB) ...")
    crc, sha = build_menu_probe.build(args.source, args.output, label=args.label, video_profile=args.video_profile,
                                      position=args.position, executable_hook=hook, payload=False)
    if args.bl_rom:
        import json
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "patcher"))
        import apply_kuro_patch as kp
        rom = kp.read_bl_rom(args.bl_rom)
        found, pos = {}, 0
        with args.output.open("rb") as f:
            while len(found) < 2:
                chunk = f.read(1 << 26)
                if not chunk:
                    break
                for tag in (kp.BL_ART_TAG, kp.SELECT_TAG):
                    k = chunk.find(tag)
                    if k >= 0 and tag not in found:
                        found[tag] = pos + k
                pos += len(chunk) - 16
                f.seek(pos)
        if len(found) != 2:
            raise ValueError("Black Label art slots not found in the built disc")
        kp.inject_bl_art(args.output, found[kp.BL_ART_TAG], kp.read_bl_art(None, rom))
        atlas = json.loads((Path(__file__).resolve().parent.parent / "patcher/bl_select_atlas.json").read_text())
        kp.inject_bl_select(args.output, found[kp.SELECT_TAG], kp.build_select_pages(rom, atlas))
        print(f"Black Label RANK bar and select screen artwork copied from {args.bl_rom}")
    print(f"\nCreated {args.output}")
    print(f"Launcher executable CRC {crc:08X}, SHA-256 {sha}")
    print(f"Boot it, press Start at the title, move to {args.label} (row {args.position + 1}), Circle: ARCADE MODE's menu with Black Label rules. EXIT returns to Mode Select.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (AssertionError, ValueError, OSError) as err:
        print("FAIL:", err, file=sys.stderr)
        sys.exit(1)
