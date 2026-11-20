# Ibara Complete — PCSX2-first Research

> **Fastest path (laptop + desktop): one clean Ibara ISO/CHD, one tiny `.pnach`. No repeated 3.66 GB image builds.**
> This is pre-alpha research, **NOT a playable Kuro / Black Label port.** No runtime patch in this new PNACH suite has yet been validated in PCSX2.

> **Black Label port (new, Nov 2026):** the plan, the measured arcade→BL delta and the first EE code-injection test are in
> [`docs/BLACK_LABEL_PORT_PLAN.md`](docs/BLACK_LABEL_PORT_PLAN.md), [`docs/BLACK_LABEL_FEATURES.md`](docs/BLACK_LABEL_FEATURES.md),
> [`research/phase11/`](research/phase11/README.md) and [`tests/manual/C00_CODE_INJECTION.md`](tests/manual/C00_CODE_INJECTION.md).
> **Runtime (2026-11-20, headless PCSX2 v1.7.4000):** C00 code injection **PASS**; K01 Black Label XTC graze runs in the attract demo (partial evidence). See [`tests/results/2026-11-20_RUNTIME.md`](tests/results/2026-11-20_RUNTIME.md).

## Start here: 60-second PCSX2 setup

1. Get **[`pnach/SLPM-66301_420C7FAB.pnach`](pnach/SLPM-66301_420C7FAB.pnach)** (~few KB). The exact filename is required: `420C7FAB` is the **original retail PCSX2 CRC**.
2. Open your PCSX2 **Tools → Open Data Directory** and copy it into **`cheats/`** (back up an existing same-named file).
3. Boot your **original unmodified** Ibara Japanese disc image; optionally use a **CHD compressed image** to save space. Confirm CRC `420C7FAB`. Enable cheats in game properties.
4. Under per-game **Cheats**, enable **one** `Ibara Complete` experiment at a time. Default: disable the experimental groups until you intend to test one.
5. Report result using [`tests/manual/RESULT_TEMPLATE.md`](tests/manual/RESULT_TEMPLATE.md). See **[`docs/PCSX2_FIRST.md`](docs/PCSX2_FIRST.md)** for the exact six patch tests, debugging addresses, and limitations.

**No retail image needed to generate/check the patches:** `python3 scripts/build_pnach.py && python3 tests/test_pnach.py`. With your clean ISO, add `--verify 'Ibara (Japan).iso'` to the generator to check original opcodes. Individual no-conflict profiles, including a no-write baseline, are in [`pnach/profiles/`](pnach/profiles/).

### Ready-to-use experiments

| ID | Patch experiment | Type | Game runtime evidence |
|---|---|---|---|
| P00 | No-write baseline | `pnach/profiles/baseline/` | Not yet recorded |
| P01 | 14-edit native 240p + nearest/crop | `.pnach` named group | Not yet recorded; residual shimmer known in separate disc patch |
| P02 | 18-edit 240p + four half-pixel coordinates | `.pnach` named group | Not yet recorded as PNACH |
| P03 | Player 1 score marker (1,000,000) | `.pnach` named group | Awaiting PCSX2 |
| P04/P05 | Easiest/hardest inverted rank locks | `.pnach` named groups | Awaiting PCSX2 |
| P06 | First medal reward 100 → 10,000 | `.pnach` named group | Awaiting PCSX2 |

**Existing research and optional 3.66 GB ISO tests are below.** The ISO-based secondary ELF boot and PDM asset injection cannot be faithfully reproduced using only PNACH memory writes, so they remain **secondary**.

---

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

### Optional: full static research validation (Windows, macOS, Linux)

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

### Optional: disk-space-intensive ISO tests (not the default workflow)

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
