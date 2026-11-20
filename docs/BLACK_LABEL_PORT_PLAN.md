# Black Label on PS2 Ibara — port plan (November 2026)

**Status (2026-11-20):** M0 done (C00 PASS in PCSX2), M1 done statically, M2 (K01 XTC) running in the attract demo. See `tests/results/2026-11-20_RUNTIME.md`.

## Is it possible?

Yes, with a large but **bounded** amount of work. Measured facts:

* The PS2 game is a direct port of the arcade structures: player-shot pool stride 0x50, enemy-bullet
  stride 0x54 and the 2^24 inverted rank all match the arcade; the player record is 0x290 vs 0x280. So arcade
  routines have recognisable PS2 counterparts.
* Black Label changes ~19% of the arcade program (Phase 11): ~27.8k SH-3 instructions of delta, 138 new
  routines. ~17k of that is regular-enemy/stage behaviour; bosses run Ibara's code and constants.
* BL's player systems (ship select, weapon stock, weapon change, XTC, shot/bomb tables) are fully
  specified (`docs/BLACK_LABEL_FEATURES.md`), and PS2 Arrange already has the closest base (stored
  sub-weapons in BL's HUD order, rank-lowering cancels).
* We can compile C for the EE and inject it into the retail game with a PNACH (`ps2/`, C00), so features
  are written as normal C against PS2 game memory, not hand-assembled patches.

## Architecture decision

| | A. Native delta port (**chosen**) | B. Run BL's SH-3 program on the EE |
|---|---|---|
| Idea | Third mode on the PS2 engine; BL's differences re-implemented as EE hooks | Recompile BL SH-3 → MIPS; translate CV1000 blitter to GS |
| Authenticity | Behaviour matched routine by routine against BL, verified by traces | By construction for logic; graphics/sound approximated |
| Hard parts | Porting ~28k-insn delta; mapping arcade ↔ PS2 routines | Own SH-3 recompiler (ibara360's is unlicensed); 128 MiB NAND graphics and a 64 MiB VRAM model on 32 MiB RAM + 4 MiB GS; YMZ770 decode; blitter blend modes the GS can't express |
| Reuses | PS2 renderer, sound, menus, saves, 240p work | Nothing from the PS2 game but the disc |
| Incremental? | Yes: each feature testable alone in PCSX2 | No: nothing visible until most of it works |

**A**, because it is incremental and every step can be tested in PCSX2 with a tiny PNACH. B stays a
reference idea: BL behaviour itself is checked against MAME/ibara360 runs of the user's own BL ROM.

## Milestones

| M | Goal | Needs | Exit test |
|---|---|---|---|
| M0 | Prove injection + collect facts | PCSX2, BIOS, clean ISO | C00 passes; cave free in title/Arcade/Arrange savestates; P00 baseline |
| M1 | PS2 fields for player x/y, camera, pad, bullet layout | savestates (protocol in `tests/manual/C00_CODE_INJECTION.md`) | `scripts/p2s_tools.py find` hits confirmed in debugger |
| M2 | **K01 XTC** live in Arcade/Arrange | M0+M1 | grazing adds 10/bullet; counter resets after 128 frames |
| M3 | Arcade ↔ PS2 routine map (`research/phase12`, built) | retail ELF | ≥ 80% of Phase 11 changed set mapped, spot-checked in debugger |
| M4 | BL mode flag: Arrange path + BL player systems (F1–F3, F5, F7, F8) | M3 | weapon stock/change and ship select play correctly |
| M5 | Stage content delta, stage 1 first | M3, BL reference runs | stage 1 enemy waves match BL video/trace frame-for-frame |
| M6 | Third menu entry, BL art from user's ROM, attract/title | M4, Phase 4 | selectable from the retail menu; Arcade/Arrange unchanged |
| M7 | ISO build (optional), 240p integration, hardware | all | B-series + H01 tests |

## Tooling now in the repository

| Path | Purpose |
|---|---|
| `research/phase11/` | arcade Ibara ↔ BL routine matcher, delta catalog, subsystem tags, anchor validation |
| `research/phase12/` | arcade SH-3 ↔ PS2 EE routine matcher (M3), offline-tested, awaiting the retail ELF |
| `ps2/` | EE hook sources (`hooks/*.c`, register-safe `stub.S`), PS2 address header with evidence levels, linker script |
| `scripts/build_ee_hooks.py` | compile + link at the cave + emit PNACH; refuses hooks that depend on unconfirmed facts |
| `scripts/p2s_tools.py` | read PCSX2 savestates (zstd ok), find fields by correlation, check the code cave |
| `pnach/hooks/h00_smoke/` | C00 profile |
| `tests/test_ee_hooks.py` | offline tests (toolchain tests skip without `gcc-mips-linux-gnu`) |

Toolchain: `apt-get install gcc-mips-linux-gnu` (Ubuntu/Debian/WSL). Flags: `-march=r5900 -EL -mabi=32
-msoft-float -mno-abicalls -fno-pic -G0`.

## What I need from you next session

1. **PCSX2 access** on the desktop (Remote Control folder) with BIOS and the clean ISO/CHD (CRC `420C7FAB`).
2. The ELF extracted or the ISO path, so `--elf` verification and the Phase 12 matcher can run locally.
3. Run **P00** then **C00** (`tests/manual/C00_CODE_INJECTION.md`), and save the savestates listed there.
4. Later (M5/M6): your own `ibarablk.zip` for BL reference runs and art. It stays on your machine.
