# Ibara Complete — Phase 3 boot-probe package

**Status:** ISO9660 file-injection verified on the exact original Japanese retail ISO. Homebrew ELF runtime execution remains untested: PCSX2/PS2 testing is required. **This is not yet a playable Ibara Kuro port or an in-game menu hook.**

## What has actually been built

- A completely original, 160-byte PlayStation 2 MIPS ELF named `KURO.ELF` (test placeholder, not arcade Black Label). It writes GS `PMODE = 0x20` to select the background layer, writes `BGCOLOR = 0x00FF00FF` (magenta), and enters an infinite loop. A magenta screen is the intended visual result, **provided video output has already been initialized**. A black screen is inconclusive; use the PCSX2 debugger to inspect execution.
- An ISO9660-only modification that inserts that ELF at LBA **500286**, registers `/KURO.ELF;1` as an ISO file, and updates the root directory metadata from **570 bytes** to **614 bytes**.
- Two output modes using a user-provided **unmodified** disc:
  - `inject`: retail `SYSTEM.CNF` and `SLPM_663.01` still boot; the added ELF is available on disc but not invoked by the game.
  - `probe`: `SYSTEM.CNF;1` points to a **new 104-byte boot configuration** at LBA **500287** that boots `KURO.ELF`. The old `SYSTEM.CNF` bytes remain at the original sector, but the filesystem entry points to the test configuration. This mode does **not** boot the retail game.

The tool needs **only Python 3.9+** and an extracted ISO. It does not need a 7z utility, PS2SDK, assembler, or external binary patch software.

## Build your test ISO

First extract `Ibara (Japan).iso` from your 7z archive, then run:

```powershell
# Windows
py -3 ibara_complete_bootstrap.py "Ibara (Japan).iso" --mode probe --output "Ibara Complete BOOT PROBE.iso"
py -3 ibara_complete_bootstrap.py "Ibara (Japan).iso" --mode inject --output "Ibara Complete RETAIL BOOT.iso"
```

```bash
# Linux or macOS
python3 ibara_complete_bootstrap.py 'Ibara (Japan).iso' --mode probe --output 'Ibara Complete BOOT PROBE.iso'
python3 ibara_complete_bootstrap.py 'Ibara (Japan).iso' --mode inject --output 'Ibara Complete RETAIL BOOT.iso'
```

Each output is the full **3,932,848,128-byte ISO**. Allow room for each copy. The source is read only and the tool refuses to overwrite existing output paths. It requires the original disc's SHA-256 to equal:

`6e58b52aa5c03d45e413e8473be52a39205095e34a1bd58dae6bd852eb4fb1db`

You can validate without writing an image using:

```bash
python3 ibara_complete_bootstrap.py 'Ibara (Japan).iso' --mode probe --dry-run
```

## What to test in PCSX2

1. Boot **`Ibara Complete BOOT PROBE.iso`** as a disc. If the firmware loads the tiny ELF and the video output is already initialized, the screen should turn **magenta** and remain that way. It will not show any text or Ibara graphics; the endless loop is intentional.
2. If the screen is black or the game fails to boot, inspect the EE program counter in the PCSX2 debugger. The program entry is **`0x00100000`**; successful execution should settle in the loop at **`0x00100018`**. That would prove the ELF handoff even if the GS video output is blank. If the EE never reaches this address, report the boot error and any logged diagnostics.
3. Boot **`Ibara Complete RETAIL BOOT.iso`**. It should start the familiar retail Ibara frontend and retain Original/Arrange behavior; the placeholder ELF is deliberately not exposed in the menu yet.
4. Use **only PCSX2 first**. This is an untested experimental boot ELF, not a verified real-console release. Do not substitute it into a finalized 240p build until the loader probe works.

**After testing:** report whether (a) probe screen turns magenta or the PC reaches `0x00100018`, and (b) the retail-boot ISO starts normally. That will establish the next objective: an actual frontend mode-selection hook and `LoadExecPS2`/loader path.

## Validation performed November 20, 2026

The build script was run against the user-supplied original ISO in *both* modes. Each output was read back by an independent ISO9660 auditor that recognized `/KURO.ELF;1`. All four original key files had their original LBAs, exact lengths and CRC32 checksums:

| File | LBA | CRC32 |
|---|---:|---|
| `SLPM_663.01` | 1919173 | `F9085060` |
| `IBARAR.PDM` | 1801312 | `F0A452FE` |
| `IBARAR.TBL` | 1920311 | `A286422C` |
| `ALLIMAGE.DAT` | 1800552 | `C09F7BED` |

Independent full-image comparison confirmed every byte **outside the allowed modification sectors** remained identical:

- PVD sector at LBA 16 (root size only)
- root-directory sector at LBA 261 (root length, new entry, and optional `SYSTEM.CNF` pointer)
- new `KURO.ELF` sector at LBA 500286
- new `SYSTEM.CNF` data sector at LBA 500287 (probe mode only)

Original disc SHA-256 remained unchanged. Runtime execution **has not** been validated. No original ISO, retail executable, copyrighted art, or soundtrack is included in this package.

## Roadmap

This is a deliberately isolated **filesystem + ELF loader** proof. Only after it boots should the work advance to:

1. PCSX2 debugger tracing of the *top-level* Original/Arrange selection, separate from Arcade and Arrange's internal menus.
2. Installing an additional Black Label option with safe input and draw hooks, **not** rewriting the original modes.
3. Linking the added option to a separate ELF using an appropriate PS2 loader mechanism, testing exit/reentry.
4. Benchmarking and integrating the real Ibara Kuro program and assets, subject to licensing, performance, and original-data constraints.

The 160-byte ELF is not an implementation of the CV1000 hardware and does not contain any arcade data.
