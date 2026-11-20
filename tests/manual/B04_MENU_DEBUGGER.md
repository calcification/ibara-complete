# B04 — Original retail frontend debugger trace (NO patch)

**Status:** NOT RUN. Use the **unmodified** ISO only, not a 240p patched build.

1. PCSX2 EE Debugger: set *execution* breakpoints from `research/phase04/PCSX2_BREAKPOINTS.txt`. Prioritize selector `0x001CA42C`, accept dispatcher `0x001CA798`, Arcade `0x001CA800`, Arrange `0x001CA824`.
2. Navigate up/down on menu, trigger each of five options in turn. Record which breakpoints fire and values of `$gp`, selected index (`-0x686C($gp)`), and frontend state (`-0x6D98($gp)` where documented).
3. Confirm transitions back to menu. Record unexpected additional calls/branches or differences from static map, including an annotated breakpoint log.
4. Verify array candidates `0x00500634`, `0x00500654`, `0x00500674` and descriptor candidates `0x002A90D8`, `0x002A90DC` are unmodified in original state. Do not write into them yet.
5. Optionally capture menu coordinates and active sprite descriptors when selecting Exit; do not trust unused pointer bytes alone to guarantee sixth-option safety.

Evidence needed: version+BIOS, EE addresses hit by each choice, registers and memory snapshots if available. A *static* `research/phase04/menu_map.json` already exists but does not replace this runtime trace.
