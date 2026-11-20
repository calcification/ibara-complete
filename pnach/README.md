# Minimal-storage PCSX2 patch files

**[Full PCSX2-first instructions](../docs/PCSX2_FIRST.md)**

- Main selectable patch: [`SLPM-66301_420C7FAB.pnach`](SLPM-66301_420C7FAB.pnach)
- Individual one-test variants: `profiles/<name>/SLPM-66301_420C7FAB.pnach`
- Each file targets the exact unmodified Japanese Ibara EE executable, CRC `420C7FAB`.
- All experiments are **unverified at PCSX2 runtime**; 19 original instruction/data anchors were checked offline.
- One active group only; cold restart between tests. Do not mix variants.
- No Black Label mode exists in the patches yet.

The group PNACH is intended for **PCSX2's cheats folder** and per-game Cheat settings. `patch=2` means apply at boot + every vsync; `patch=1` every vsync. Before copying, back up any existing same-named PNACH.

Regenerate with `python3 scripts/build_pnach.py`. Optionally add `--verify /path/to/retail.iso` to verify all source preimages. The generator never rewrites your ISO.
