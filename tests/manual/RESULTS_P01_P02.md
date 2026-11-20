# P01 and P02 · 240p video profiles in PCSX2

**Result:** PASS for patch application and progressive GS output. PCSX2 2.8.2 on Linux used Japanese BIOS v01.00 and Mesa OpenGL. Each run cold-booted the exact Japanese retail ISO, serial `SLPM-66301`, CRC `420C7FAB`, with both memory cards disconnected. P00 used no cheats. P01 and P02 used their individual PNACH files, with one named group active in each run.

| Run | EE memory snapshot | GS `SMODE2` | GS `DISPLAY2` active height | GS `DISPLAY2.DY` |
|---|---|---|---|---|
| P00 baseline | All 18 checked words matched retail | `0x03` (interlaced) | 448 lines | 50 |
| P01 core | All 14 core writes applied; the 4 additional coordinate sites matched retail | `0x02` (progressive) | 224 lines | 25 |
| P02 half-pixel | All 18 writes applied | `0x02` (progressive) | 224 lines | 25 |

The PCSX2 boot log reported NTSC at nominal 59.94 Hz in all three runs. The log's initial mode announcement lists a nominal 640×448 geometry. The dump of the live display registers establishes the 224 active lines on read circuit 2 for P01 and P02, with its horizontal origin and width matching P00. The core and half-pixel variants used identical display-register settings.

The matched 640×480 emulator screenshots of the startup memory-card prompt for P01 and P02 differed only inside the 48×6 pixel selection underline. Judge shimmer and fine registration with matched moving captures and on a physical CRT. This run establishes emulator scan mode, active geometry, and the four extra coordinate writes. It leaves the relative motion quality and the physical video signal open.

Both profiles reached Arcade gameplay. P02's gameplay check used a separate blank memory card and reconfirmed all 18 EE words and 224 active progressive lines. A read-only comparison of the M02 launcher image found all 18 original video words intact under its different executable CRC. The combined launcher and video configuration still needs its own runtime check.

## Reproduction

1. Follow the [PCSX2-first setup](../../docs/PCSX2_FIRST.md) with a separate cold boot for each profile. Keep the renderer, scaling, and deinterlacing settings fixed.
2. At the startup prompt, capture a GS dump with Shift+F8 and an EE-memory snapshot with F1 using the default PCSX2 bindings. Repeat at a gameplay screen for an additional check.
3. Compare `eeMemory.bin` from the save state against the 18 EE word addresses in `scripts/build_pnach.py`. Inspect `SMODE2` (offset `0x20`) and `DISPLAY2` (offset `0xA0`) in the GS dump's privileged register block. `SMODE2` bit 0 controls interlace. `DISPLAY2[54:44] + 1` gives the active height.
