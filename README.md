# Ibara Complete — PS2 Original + Arrange + Black Label Research

> **Research / pre-alpha handoff — NOT a playable Black Label PS2 port.**
> The existing retail PS2 **Arcade** and **Arrange** modes have not been modified into a tested third game mode. No PS2/PCSX2 boot test of the injected secondary ELF has yet been reported.

This repository is the reproducible technical handoff for a project investigating a **third authentic Ibara Kuro / Black Label mode** in the Japanese PS2 *Ibara* (`SLPM_663.01`), alongside the existing retail modes. It is **not** the existing 240p patch release; that is maintained at [calcification/cave-ps2-240p](https://github.com/calcification/cave-ps2-240p).

### What is actually available

- Full retail ELF/ISO metadata and 1,130-item resource catalog (Phases 1–2)
- **Two experimental ISO boot tests**: inject a 160-byte original test ELF without changing retail boot, or boot that ELF instead (Phase 3)
- Retail mode-select address map and **in-place prototype button generator** (Phase 4; no menu hook, invisible in game)
- Bounded CV1000 VRAM/NAND memory prototype with host-side tests and a MIPS III object (Phase 5)
- Read-only, instruction-fingerprinted audits for native PS2 input, rank, pickups, medal scoring, bullet conversion, and rose merging (Phases 6–10)
- Cross-platform scripts, `TEST_MATRIX.csv`, a full manual PCSX2/PS2 checklist, and a reproducible audit runner

**Read first:** [HANDOFF](docs/HANDOFF.md) · [CURRENT STATUS](docs/STATUS.md) · [ALL TESTS](docs/TESTING.md) · [ERRATA](docs/ERRATA.md).

### Quick start — research validation (Windows, macOS, Linux)

Requirements: Python **3.10+** and your own clean, unmodified Japanese `Ibara (Japan).iso`.

Windows PowerShell:

```powershell
py -3 scripts/run_audits.py "Ibara (Japan).iso" --out validation-output
```

macOS/Linux:

```bash
python3 scripts/run_audits.py 'Ibara (Japan).iso' --out validation-output
```

This runs the static auditors and their original-ELF-dependent unit tests. It **does not** modify the game. Results are stored in `validation-output/` (gitignored). Use `--full` for the optional checksum-intensive Phase 3 dry runs, zero-gap scan, and Phase 5 C compiler test. Running `python3 scripts/run_audits.py --selftest` does not require any game ISO and tests the Phase 5 standalone tools.

### Prepare boot images — only when ready for PCSX2

```bash
python3 scripts/build_test_images.py 'Ibara (Japan).iso' --mode probe --out outputs
python3 scripts/build_test_images.py 'Ibara (Japan).iso' --mode inject --out outputs
```

The original ISO is preserved. Each output is ~3.66 GiB; **do not** upload outputs to this repository. Start with PCSX2; do not use the boot probe on original hardware until verified in an emulator. See [TESTING](docs/TESTING.md).

Optional preview/test of the dormant Black Label button:

```bash
python3 -m pip install -r requirements-assets.txt
python3 scripts/build_test_images.py 'Ibara (Japan).iso' --mode asset --out outputs
```

This is an **asset-only** change: the original retail five-item menu still displays five items. No new mode is enabled.

### Version-specific safety

Verified clean ELF SHA-256: `263d3079dee66af82815219351553075340a4d9f42aceaa7bb8ef2bfb812ffac`.

Verified clean ISO SHA-256: `6e58b52aa5c03d45e413e8473be52a39205095e34a1bd58dae6bd852eb4fb1db`.

**Do not run original-retail auditors against the already 240p-patched ISO**: intentional instructions differ. The separate 240p work remains the long-term video baseline, but compatibility has **not** been demonstrated by these prototype ISOs.

No commercial game assets or programs are distributed. The small `KURO_PROBE.ELF` is our own synthesized 160-byte test program, **not** Ibara Kuro. You must supply legally obtained game data locally. The public `ibara360` project is cited for technical comparison but its generated SH-3 code is **not** bundled or relicensed here.

### Current confidence model

- **Static verified:** a byte or instruction matches the specific clean retail revision.
- **Inferred:** a semantic explanation consistent with the instructions but not behaviorally measured.
- **Runtime untested:** a patch or injection passed offline structural checks but not PCSX2 or console execution.
- **Runtime verified:** requires an attached reproducible log/video/GS dump and exact revision details.

**Contributors and other models:** do not equate the first three with the fourth. Preserve the original retail Arcade/Arrange modes and do not publish a Kuro success claim without the appropriate tests.
