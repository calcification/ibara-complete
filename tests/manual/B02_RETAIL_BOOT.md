# B02 — Retail boot + injected extra ELF (PCSX2)

**Status:** NOT RUN. **Input:** exact clean retail ISO.

1. Build: `python3 scripts/build_test_images.py "Ibara (Japan).iso" --mode inject --out outputs`
2. PCSX2: first boot the clean ISO to establish working baseline, then boot `outputs/Ibara Complete RETAIL BOOT.iso`.
3. Compare: title screen; select Arcade Mode, enter and exit; select Arrange Mode, enter and exit; Gallery, Option, Exit. Verify both gameplay modes still start without a crash. Check whether saves and memory-card files appear consistent. Record each step separately.
4. **Expected:** exactly five mode choices; no new Black Label option yet. The newly injected `KURO.ELF;1` should not be launched by retail code.
5. Report PCSX2 version, BIOS, renderer, EE exception or debug state on any fault. Record each menu branch, not just 'boot okay'.

**This does not test native 240p** or actual Black Label.
