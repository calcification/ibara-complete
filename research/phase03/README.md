# Ibara Complete — Phase 3 boot-probe package

**Status:** ISO9660 file injection has been verified offline on the original Japanese retail ISO. The homebrew ELF and synthetic disc boot paths have run in Play! 0.70. Retail PCSX2 tests B01 and B02 are pending.

## What has actually been built

- A completely original, 160-byte PlayStation 2 MIPS ELF named `KURO.ELF` (test placeholder, not arcade Black Label). It writes GS `PMODE = 0x20` with both read circuits disabled, writes `BGCOLOR = 0x00FF00FF` (magenta), and enters an infinite loop. A magenta screen is the intended visual result, **provided video output has already been initialized**. A black screen is inconclusive. Use the PCSX2 debugger to inspect execution.
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
3. Boot **`Ibara Complete RETAIL BOOT.iso`**. Check the retail Ibara frontend and repeat the Arcade and Arrange checks from the unmodified disc.
4. Complete both PCSX2 disc tests before attempting them on a real PS2 or combining the changes with the 240p build.

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

Original disc SHA-256 remained unchanged. Retail runtime tests are pending. No original ISO, retail executable, copyrighted art, or soundtrack is included in this package.

### Homebrew-only runtime check

Play! 0.70 on Linux executed the standalone fixture and both builder outputs from an 80 KiB synthetic ISO. The unmodified synthetic disc and `inject` output booted its original homebrew ELF. The `probe` output booted `KURO.ELF;1`. In each case the save state showed EE PC `0x00100018`. Register `$t1` held `0x0000FF00` for the synthetic disc's original executable and `0x00FF00FF` for the probe, distinguishing the two payloads even with blank video. B01 and B02 require the exact retail image in PCSX2.

Run `python3 tests/test_bootstrap.py` from the repository root to reproduce the offline fixture and ISO checks. The test uses only synthetic input and also verifies that a failed exclusive create preserves a competing builder's output.

## Roadmap

Start with the clean-disc P00 baseline and B04 menu trace in the [PCSX2 test plan](../../docs/PCSX2_FIRST.md). Use B01 and B02 when evaluating the on-disc ELF path. For menu integration, proceed in this order.

1. Trace the top-level Arcade and Arrange selections in the PCSX2 debugger and confirm all five existing options.
2. Add an isolated test option with input and draw hooks based on the trace.
3. Launch the homebrew ELF from the test option and verify the handoff, exit, and reentry.
4. Evaluate a compatible executable and its data after the test option and loader pass regression checks.

The 160-byte ELF is not an implementation of the CV1000 hardware and does not contain any arcade data.
