# B01 — Standalone secondary-ELF boot probe (PCSX2 first)

**Status:** NOT RUN / awaiting tester. **Input:** exact clean Japanese retail `Ibara (Japan).iso`. **Files provided:** `research/phase03/ibara_complete_bootstrap.py`, `tests/fixtures/KURO_PROBE.ELF`, `research/phase03/probe_source.s`.

1. `python3 scripts/build_test_images.py "Ibara (Japan).iso" --mode probe --out outputs`
2. Boot `outputs/Ibara Complete BOOT PROBE.iso` in PCSX2, with logging and EE debugger available.
3. Expected: purple/magenta background **if GS output is initialized**. This is only a convenience; blank output is **inconclusive**.
4. Pause EE CPU. Probe ELF entry is `0x00100000`; loop/settled EE PC is `0x00100018`. If observed, record evidence of program execution even with black screen. If not reached, record BIOS/OSDSYS error, loader log, and nearest PC.
5. Confirm the retail menu did **not** appear (this probe replaces only the boot config). Report PASS if secondary ELF execution is observed, FAIL only with supported loader evidence, or INCONCLUSIVE otherwise.
6. Save screenshot (if available), startup log, PC, emulator version, BIOS region and renderer. Fill `tests/manual/RESULT_TEMPLATE.md`.

**What it does not test:** a Kuro game mode, menu hook, native 240p, or safe hardware execution. Do not perform on real PS2 yet.
