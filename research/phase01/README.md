# Ibara Complete — Phase 1 Structural Analysis

**Date:** 2026-11-19  
**Target:** Japanese retail PS2 `SLPM_663.01`  
**Status:** Static ELF inspection complete; retail disc directory and runtime tracing pending  
**Safety:** No executable or ISO modifications have been made.

## Scope and source integrity

Recovered three previously uploaded copies of the PS2 executable (`SLPM_663(1).01`, `(2)`, `(3)`). All were byte-for-byte identical. SHA-256:

`263d3079dee66af82815219351553075340a4d9f42aceaa7bb8ef2bfb812ffac`

The publicly distributable package must not include this retail binary, the retail ISO, or Cave's arcade ROMs. The accompanying JSON and Python file contain only analysis/metadata and a read-only auditor.

## ELF format and memory

| Finding | Value |
| --- | --- |
| Format | ELF32, little-endian MIPS, executable |
| Compiler string | `MW MIPS C Compiler (2.4.1.01)` |
| File length | 2,329,648 bytes |
| Entry point | `0x00100008` |
| Main load (file offset) | `0x00000080` |
| Main load (virtual address) | `0x00100000` |
| File-backed load length | `0x00238A00` = 2,329,088 bytes |
| Memory length requested | `0x00401F00` = 4,202,240 bytes |
| Load's file-backed versus memory delta | 1,873,152 bytes (not evidence of available free memory) |
| `.symtab` | Empty; no usable linker symbol names |
| Prior project's ISO LBA for ELF | 1,919,173 (not reverified from disc here) |

Conversion for this ELF's first PT_LOAD: `file_offset = RAM_address - 0x00100000 + 0x80`. The original 240p ISO mapping in the prior patcher additionally adds `1,919,173 × 2048` for the disc extent. **ISO file placement has not yet been verified in this session.**

## Actual mode-menu tables

All four tables below are decoded from the ELF's pointer data (rather than inferred from screenshots). The pointers lead to ASCII strings within the same ELF:

| Table | File offset | EE address | Entries |
| --- | --- | --- | --- |
| Arcade main | `0x1A90A0` | `0x002A9020` | GAME START / PRACTICE / CONFIG / EXIT |
| Arrange main | `0x1A90C8` | `0x002A9048` | GAME START / CONFIG / EXIT |
| Arrange options | `0x1A90E0` | `0x002A9060` | FIGHTER TYPE / BULLET DESIGN / KEY CONFIG / EXIT |
| Arcade difficulty | `0x1A9180` | `0x002A9100` | NORMAL / HARDER / EXTENDED / EXIT |

Japanese help text at file offset `0x1A9160` identifies the arcade mode, while further Japanese text around `0x1A94A0` explicitly describes Arrange-mode options. The top-level mode selection may still be rendered from external assets: these tables establish *internal mode menus*, not the top-level artwork or dispatch.

## Static control-flow evidence

Addresses below are EE execution addresses (not ISO offsets), decoded using LLVM's MIPS disassembler:

| Address | Evidence | Interpretation |
| --- | --- | --- |
| `0x001CA974` | `lui $s2,0x2b` and `addiu ..., -0x6fe0` | Builds address of Arcade main menu table |
| `0x001CCAE4` | `lui $s2,0x2b` and `addiu ..., -0x6fb8` | Builds address of Arrange main menu table |
| `0x001CABD0` | `lui/addiu` references Arcade difficulty table | Difficulty submenu is separate |
| `0x001CCDDC` | Nearby `lui/addiu` reference to Arrange options | Arrange's option flow is separate |
| `0x001CAA88` | Loads menu selection from `-0x686c($gp)` and branches on 0/1/2/3 | Arcade input/accept dispatcher |
| `0x001CCBF4` | Loads selection from `-0x686c($gp)` and branches on 0/1/2 | Arrange input/accept dispatcher |

**Arcade accept switch (verified instructions):**

- Selected index 0 branches to `0x001CAAE8`: writes 3 to `-0x6d98($gp)`.
- Index 1 branches to `0x001CAB0C`: writes 4 to `-0x6d98($gp)`.
- Index 2 branches to `0x001CAB38`: writes 6 to `-0x6d98($gp)`.
- Index 3 falls into `0x001CAAC4`: writes 1 to `-0x6d98($gp)`.

This looks like an **internal frontend state variable**. We have not yet confirmed which subsequent routines perform loading or gameplay initialization.

**Arrange accept switch (verified instructions):**

- Index 0 branches to `0x001CCC44`: writes 1 to `-0x6dac($gp)` and initiates another transition.
- Index 1 branches to `0x001CCC6C`: writes `0xA` to `-0x6d98($gp)`.
- Index 2 falls into `0x001CCC20`: writes 1 to `-0x6d98($gp)`.

The menu-selection cursor at `-0x686c($gp)` is reused by both paths. Another variable at `-0x6864($gp)` is written with 0 in the Arcade path and 1 in the Arrange path at corresponding transitions; it is a *candidate* mode flag, not confirmed.

## Asset access and disc architecture

The ELF contains the literal string `cdrom0:\IBARAR.TBL;1` at file offset `0x001ACD40`; a code reference to that string was found near EE `0x0010BE48`. It also names individual IOP modules (such as `mtsfile.irx`, `mtssound.irx`, `mtsmovie.irx`), but those text references do not prove where modules or game artwork physically reside on disc.

The external `ibara360` project includes `tools/ps2extract`, which builds PS2 frontend and soundtrack data from the retail ISO. Its README reports that it uses PS2 mode-selection/loading UI and the PS2 soundtrack in its Xbox 360 port. This independently reinforces that the original ISO contains reusable frontend assets; it does not prove that it contains Ibara Kuro's complete arcade program or artwork.

Source: https://github.com/PaulAtreides67/ibara360

## Relationship to the existing 240p patch

Seven sampled known locations from the Ibara 240p project's original-word patch list matched the expected unmodified retail instructions. These include output mode, texture filtering, a UV crop entry and the three field-related instructions. This verifies the executable is a suitable original baseline for further *analysis*; it does not certify the 240p beta's remaining shimmer is solved.

Recommended release architecture: a user-supplied **unmodified** Japanese ISO becomes the only retail image input; the patcher validates its content and writes a *new copy*, first applying only established 240p changes, then installing separately tested Ibara Complete functionality.

## Architecture decision and constraints

**Recommended:** preserve the retail frontend and both retail modes; add a third top-level Black Label entry that launches a separate Kuro runtime, *if it proves viable*. Avoid modifying existing Arcade's three Normal/Harder/Extended options: those are game variants already within Arcade, not the top-level choices. A separate ELF avoids simultaneously resident original and Kuro engines, but has not yet been tested. Rebuilding Kuro directly within the existing PS2 Arrange runtime remains an alternative worth assessing before committing to any architecture.

The retail ISO requirement does **not** automatically eliminate the need for Black Label arcade program and asset data. The reference Xbox 360 project explicitly requires `ibarablk` ROM data in addition to the PS2 ISO. A complete and authentic Kuro PS2 conversion must either (1) use separately user-provided Kuro arcade data, (2) reimplement original behavior with permitted and sufficient existing assets, or (3) demonstrate an independently legal way of supplying the missing material. Do not assume a two-megabyte executable can itself supply every arcade asset.

The `ibara360` repository does not prominently advertise a license in its root file list. Review the code license and contact its author before copying or redistributing its recompiled implementation. Adaptation to EE MIPS, 32 MB system RAM, 4 MB GS VRAM, SPU2, and CD/DVD access is a separate performance and compatibility effort.

## Required next checks before patching a menu

1. Run the accompanying read-only auditor on the complete retail ISO. Record ISO directory entries, extents, sizes, hashes, `SYSTEM.CNF`, `SLPM_663.01`, and `IBARAR.TBL` placement. Compare the boot ELF hash to the one above and confirm the boot extent matches the earlier LBA.
2. Trace the **top-level Arcade/Arrange selector**, not just the internal four-entry/three-entry menus. Use PCSX2 debugger breakpoints on writes to `-0x6d98($gp)` and `-0x6864($gp)` and on the execution addresses above, with the runtime GP value recorded.
3. Find the real scene transition to gameplay and how the game restarts its frontend after exiting. Verify where assets are loaded and whether modes are implemented as shared engine branches.
4. Investigate whether `IBARAR.TBL` indexes game archive assets and whether existing front-end textures have room for a third selectable mode. Do not modify the disc before this is understood.
5. Benchmark a minimal, headless PS2 Kuro logic executable and its memory demands before planning graphics/audio integration.
6. Preserve separate save data for Kuro and retain a byte-identical retail path when Kuro is never selected.

## Running the audit tool

`python ibara_complete_audit.py "Ibara (Japan).iso" --json iso-audit.json`

Or audit a directly extracted original ELF:

`python ibara_complete_audit.py SLPM_663.01 --json elf-audit.json`

Works with Python 3 standard library on macOS, Windows and Linux. Plain 2048-byte-sector ISO9660 inputs are supported, not compressed CHD/ZSO or 2352-sector raw BIN. The script is read-only and produces a metadata report only. It was tested against the recovered ELF and a synthetic ISO9660 fixture. **The actual retail ISO was not available in this session**, so the full disc file map is not yet known.
