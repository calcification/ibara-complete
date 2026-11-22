# Next project: Mushihimesama Complete

After Ibara Complete, the plan is **Mushihimesama Complete**: a "complete version" fix for the PS2
Mushihimesama. That port is also a Cave game ported by Taito, so it is likely built on the same engine and SDK
practices as PS2 Ibara. This file lists what from this repository should carry over, and what to check first.
Everything said about Mushihimesama here is an **expectation to verify**. None of it has been checked against that
disc yet.

Keep this repository's tooling, research scripts and notes. They are the starting kit.

## Reusable as-is (game-independent)

| What | Where | Notes |
|---|---|---|
| EE hook toolchain (C/asm → baked image, hook stubs, runtime word tables) | `scripts/build_ee_hooks.py`, `ps2/link.ld`, `ps2/hooks/stub.S` | Build with **n32** (`-mabi=n32`, `ld -m elf32ltsmipn32`); see the lessons below |
| Extra PT_LOAD segments in the executable (`bake_elf(..., extra)`) | `scripts/build_ee_hooks.py` | For code or data at a fixed address, loaded with the ELF |
| Disc rebuild with a moved or enlarged executable | `scripts/build_black_label_iso.py`, `research/phase04/build_menu_probe.py` | ISO 9660 root-directory edits, same ISO size |
| Patch format that ships no game data (COPY from the retail disc or ELF + small DATA) | `scripts/make_patch.py`, `patcher/apply_kuro_patch.py`, `.bat` | Change only the source size, MD5 and file names |
| Optional art from the user's own arcade ROM (tagged segment, filled by the patcher after a CRC check) | `patcher/apply_kuro_patch.py` (`read_bl_rom`, tags `...-ART-01`/`-ON`) | Same pattern works for any MAME set |
| Repository safety check (no ISO/ELF/ROM/savestates committed) | `scripts/check_repository_safety.py` | Run before every commit |
| PCSX2 headless driving, savestate RAM reads, PINE | `scripts/pcsx2_headless.py`, `scripts/p2s_tools.py`, `scripts/pcsx2_pine.py` | `p2s_tools.load_ee` reads eeMemory from a `.p2s`; cpuRegs and CP0 sit in "PCSX2 Internal Structures.dat" after the `cpuRegs` tag |
| MAME Lua capture or loggers (blitter draws, uploads, kill/write taps, per-frame state) | `research/phase20/*.lua`, `tools/stage_compare/*.lua` | Cave's later boards (CV1000 / SH-3) share the blitter; Mushihimesama is CV1000 too |
| Stage-by-stage PS2-vs-MAME comparison harness | `tools/stage_compare/`, `run_stage.py` | Part HP tables, fire timers, cancel triggers, rank |

## Expected engine similarities (verify each)

On PS2 Ibara (SLPM-66301) these facts were read from the executable. Look for the same routines in
Mushihimesama by pattern, not by address:

- **Sprite routine** like `0x00110B70(flags, col<<8|u, row<<8|v, tint, f12 x, f13 y, f14 w, f15 h)`. Flags
  0x10000000 | (arcade attr & 0x277)<<16 | flips | alpha. This is the arcade blitter's attribute word passed almost
  directly, so arcade blend modes map one-to-one.
- **Texture page table** (row*32+col → object index), 60-byte objects, prebuilt GS upload descriptors (+0xC4 cache
  slot), and a GS texture **cache** of 260-block slots with second-chance eviction (`0x001BB090`). Our own
  PSMCT16 pages cloned from a HUD object worked (`ps2/hooks/bl_tex.c`).
- **Main loop**: draw pass with 24 priority layers, then the HUD calls, then a pause byte that skips the game update
  and calls the pause menu. That is a clean place for full-screen overlays (`ps2/hooks/bl_select.c`).
- **gp-relative globals** (Ibara: gp = 0x0033FCF0): frame counter, rank, HUD offsets, pause byte.
- **Enemy part pool** with +0x04 type / +0x08 subtype / +0x3C HP, a **bullet pool** of 256 × 0x54, and a shared
  fire timer `base + factor * (rank >> 16) / 256`. Arcade field offsets were kept.
- **Frontend** state machine with menu rows, a dispatcher, help text pointers, and a CONFIG row table that has spare
  rows (Ibara phases 4 and 17).

## Lessons that cost the most time (apply from day one)

1. **Stack alignment.** Taito's EE code spills 128-bit registers with `sq`/`lq`. The kernel saves a preempted
   thread's registers on its own stack the same way. o32 C code (8-byte frames) corrupted `gp` at random after a
   thread switch. **Build hook C as n32** (16-byte frames). Keep the test that checks every `addiu sp`.
2. **Leaf hooks.** Code entered from the middle of game functions must not use s-registers (`-ffixed-s0..s7`,
   `-ffixed-fp`), because the game keeps 128-bit values there.
3. **`jal` delay slot**: `ra` is already overwritten there, so never save `ra` in it.
4. **Debug method that worked**: a local PCSX2 build whose TLB-miss message prints `pc/gp/sp/ra`
   (`pcsx2/vtlb.cpp`). Add register checks (first bad value plus caller) inside our own wrappers and read them from
   savestates. For a frozen thread, search eeMemory for its saved register block below its stack pointer.
5. Re-read symbol addresses after every build (sizes shift).
6. Don't open overlays during loading (texture tables are rebuilt). Wait for the game's own "pausable" condition.
7. **The ISO must never grow** (user rule): new code and art go into existing disc space; tools refuse a larger
   image.
8. **Ship nothing copyrighted.** Art comes from the user's ROM at patch time. Generated tables hold coordinates only.

## First steps for Mushihimesama

1. Identify the disc (serial, size, MD5) and the executable. Find the main loop, the gp value, the sprite routine
   and the texture table by the patterns above.
2. List what "complete" means for that port (missing modes, arcade-accurate rules or rank, video modes,
   menu entries), like `docs/BLACK_LABEL_FEATURES.md` here.
3. Copy the toolchain, patcher and safety check. Switch the file names, hashes and the bake region (check that it
   stays zero in savestates and lies outside the main stack: Ibara's main stack is the top 1 MB of RAM).
