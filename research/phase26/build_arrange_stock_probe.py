#!/usr/bin/env python3
"""Build either Arrange player-stock prototype as a retail-only PCSX2 profile."""
import argparse
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import build_ee_hooks as hooks
import build_pnach as pnach

PATCHES = [
    (0x001CCDCC, 0x3C15002B, "hi", "arrange_stock_labels"),
    (0x001CCDDC, 0x26B59060, "lo", "arrange_stock_labels"),
    (0x001CCEBC, 0x2A220004, "raw", 0x2A220005),
    (0x001CCFC8, 0x28410004, "raw", 0x28410005),
    (0x001CCE68, 0x16220007, "j", "arrange_stock_value"),
    (0x001CD058, 0x1000FFFA, "j", "arrange_stock_wrap"),
    (0x001CD05C, 0xAF829794, "raw", 0x24020004),
    (0x001CD09C, 0x1462FF44, "j", "arrange_stock_accept"),
    (0x001CCED4, 0x3C02002B, "hi", "arrange_stock_help"),
    (0x001CCEDC, 0x24429420, "lo", "arrange_stock_help"),
    (0x001CCEF8, 0x3C02002B, "hi", "arrange_stock_help", 4),
    (0x001CCEFC, 0x24429424, "lo", "arrange_stock_help", 4),
    (0x0012D8E8, 0x14600003, "j", "arrange_stock_start"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("retail", type=Path)
    parser.add_argument("--mode", required=True, choices=("rows", "copy"))
    parser.add_argument("--output", type=Path, required=True, help="PCSX2 cheats directory")
    args = parser.parse_args()
    key = "arrange_stock_probe"
    hooks.HOOKS[key] = {
        "test_id": "A01",
        "title": f"Arrange player stock prototype ({args.mode})",
        "description": "Enable this profile alone on the original PS2 disc, then open Arrange Config.",
        "sources": ["arrange_stock_probe.c"],
        "stubs": [],
        "sites": [],
        "sym_patches": PATCHES,
        "defines": ["ARRANGE_COPY_STOCK"] if args.mode == "copy" else [],
    }
    hooks.LEAF_SOURCES.add("arrange_stock_probe.c")
    retail = pnach.load_elf(args.retail)
    with tempfile.TemporaryDirectory() as work:
        built = hooks.build_hook(key, Path(work))
    hooks.verify_sites(retail, built)
    text = pnach.HEADER + "\n" + hooks.pnach_group(hooks.HOOKS[key], built)
    pnach.check_pnach(text, min_addr=hooks.CAVE_BASE)
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / pnach.NAME).open("x", encoding="utf-8") as output:
        output.write(text)


if __name__ == "__main__":
    main()
