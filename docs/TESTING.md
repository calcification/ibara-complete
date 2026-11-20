# Current priority: PCSX2 patch tests P00–P06

**Use [`PCSX2_FIRST.md`](PCSX2_FIRST.md) before the legacy test procedures below.** The original ISO/CHD plus `pnach/SLPM-66301_420C7FAB.pnach` supports all current video/rank/score/medal experiments with no new game images. The B01–B03 ISO builds below are **optional, postponed** and cannot simply be translated into PNACH. `B04` needs the original disc and debugger only. [P01 and P02 have passed in PCSX2](../tests/manual/RESULTS_P01_P02.md). P03–P06 are pending.

---

# Complete testing plan — run in order

**Nothing below implies that a runtime test already passed.** The tests in the previous phases were primarily *offline checks*; the boot and graphical tests have not been reported back yet. Begin with `TEST_MATRIX.csv` for a machine-readable checklist. Save outcomes using `tests/manual/RESULT_TEMPLATE.md`.

## Required files and where they come from

- `Ibara (Japan).iso`: YOU supply your legally obtained **unmodified** Japanese PS2 disc image (SHA: `6e58...` listed in `README.md`). **Not distributed here.** Do not substitute an already progressive/240p-patched ISO.
- `SLPM_663.01`: extracted automatically by `scripts/run_audits.py` to a temporary folder; you do not need to manually supply it.
- `KURO_PROBE.ELF`: repository-provided *homebrew*, 160 bytes at `tests/fixtures/KURO_PROBE.ELF`; `research/phase03/ibara_complete_bootstrap.py` includes its own exact synthesized payload.
- PCSX2, a working standard retail ISO boot setup and the EE debugger: install locally; not supplied.
- For optional Phase 4 texture generation: `pip install -r requirements-assets.txt`. This produces a local PNG from your own ISO, which **must not be committed**.
- For optional arcade ROM fingerprint test: supply the original `ibarablk.zip` legally; no ROM data is in this repo.
- For hardware: actual Japanese-disc-capable homebrew setup, display and capture device; start only after emulator tests.

## Offline baseline and static tests — you can run these immediately

Windows: `py -3`; macOS/Linux: `python3` in examples. Python 3.10+.

```bash
python3 scripts/run_audits.py 'Ibara (Japan).iso' --out validation-output
```

It runs Phase 1, 2, 4, 6–10 auditors, Phase 6–10 test suites, and Phase 5 Python synthetic tests. It checks that the extracted 2,329,648-byte retail ELF matches SHA-256. The program returns nonzero on failure, writes a JSON summary and individual logs into `validation-output`, and never writes the source.

Full extra checks (slower):

```bash
python3 scripts/run_audits.py 'Ibara (Japan).iso' --out validation-output --full
```

Also performs Phase 2 full 2.66 GB gap scan, both Phase 3 SHA-verifying dry runs, Phase 5 C native unit tests (when a C compiler is available). To run synthetic Phase 5 tests **without** any game image:

```bash
python3 scripts/run_audits.py --selftest --out validation-output
```

Optional Kuro ROM metadata/payload verifier (not a gameplay test):

```bash
python3 research/phase05/src/check_kuro_roms.py /path/to/ibarablk.zip --verify-payload
```

## Runtime boot and menu tests

The [P00 and B04 results](../tests/manual/RESULTS_P00_B04.md) cover the unmodified retail frontend. Disc tests B01–B03 are pending.

**Test B01 / `BOOT PROBE`:** Build from original:

```bash
python3 scripts/build_test_images.py 'Ibara (Japan).iso' --mode probe --out outputs
```

Boot `outputs/Ibara Complete BOOT PROBE.iso` in PCSX2. **Expected:** an intended magenta GS background, OR use EE debugger to see instruction pointer settle at `0x00100018` (this secondary observation is authoritative if the display stays black). Probe entry is `0x00100000`. Capture startup log, PC address and screenshot; no normal game should boot in this variant. See [B01 procedure](../tests/manual/B01_BOOT_PROBE.md).

**Test B02 / `RETAIL INJECTION`:**

```bash
python3 scripts/build_test_images.py 'Ibara (Japan).iso' --mode inject --out outputs
```

Boot `outputs/Ibara Complete RETAIL BOOT.iso` in PCSX2; standard frontend should appear. Check Arcade, Arrange, Gallery, Option, Exit and returning to title. The third option is **NOT** expected. Compare with original retail ISO. See [B02 procedure](../tests/manual/B02_RETAIL_BOOT.md).

**Test B03 / `ASSET ONLY`:** Requires Pillow/numpy:

```bash
python3 -m pip install -r requirements-assets.txt
python3 scripts/build_test_images.py 'Ibara (Japan).iso' --mode asset --out outputs
```

Check `outputs/Ibara Complete ASSET ONLY.iso` boots normal five-entry retail frontend. The new button should **not** be visible, because there is still no sixth drawing call. Compare the generated `outputs/Phase4_Button_Prototype.png` with the original sprite page. See [B03 procedure](../tests/manual/B03_ASSET_ONLY.md).

**Test B04 / `MENU DEBUGGER`:** No modified game required. Boot the ORIGINAL retail ISO and add execution breakpoints at the listed EE addresses in `research/phase04/PCSX2_BREAKPOINTS.txt`. Observe selector, Arcade accept, Arrange accept, Gallery/Option/Exit and returning to menu. Collect address, event and mode. See [B04 procedure](../tests/manual/B04_MENU_DEBUGGER.md).

**Test H01 / REAL PS2:** **Blocked pending successful PCSX2 B01–B03.** Test only the safe retail-injected image first; evaluate secondary homebrew ELF on real hardware only after stability/compatibility is established. Match GS mode to CRT. See [H01 procedure](../tests/manual/H01_REAL_PS2.md). Do not mistake normal composite or RGB sync behavior for proof of native 240p.

## Tests NOT POSSIBLE YET

- A visible, selectable third BLACK LABEL entry — no code hook implemented.
- `KURO.ELF` executing genuine arcade Kuro code — test ELF is only a magenta loop.
- 240p + new-mode integration — no combined build yet.
- Kuro scoring/XTC parity, audio, original hardware performance or frame pacing — no playable Kuro port yet.

Do not fill these with PASS; keep them **BLOCKED / NOT IMPLEMENTED**. No user screenshot is needed for the static auditors. A repeatable manual run requires identifying PCSX2 version, renderer, BIOS region, CRC, exact output ISO, and result observations.
