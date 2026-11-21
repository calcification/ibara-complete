# Phase 20 — Black Label's ship select screen: inventory (2026-11-22)

**Only in Black Label.** The select screen is BL-only code (`0C0B8210`, 1,618 instructions, with `0C070DC0`,
`0C0703C0`, `0C0734D0`; Phase 11 found no arcade Ibara counterpart). Arcade Ibara and the PS2 port have no select
screen: the pilot is the side (P1 Bond, P2 Dyne) and PS2 sets the type in CONFIG > FIGHTER TYPE. The PS2 disc's
textures (`IBARAR.PDM`, 1,113 TIM2) hold the GALLERY sketches and one colour ship illustration, none of this screen.

**What it shows** (MAME snapshots): 武機選択 header with a 60-s timer; per player a metal panel with the pilot (P1 Bond,
P2 a second pilot with blue ships), the ship's name (シスター・シミリス straight, ディオ・スピロッソ spread),
直進型 / 拡散型 labels, a large ship render; a 参戦可能 "join" panel for the free side; 左右で機体を選択 prompt; a girder
background that fades in; a dissolve / fly-in transition when the ship changes.

**How it is drawn.** Blitter job lists in RAM (`0C3CC400` / `0C46C500`, double-buffered); draw op = 10 BE words
(attr 0x1xxx: d_mode, s_mode, trans, blend, flipy, flipx; alpha; src x, y; dst x, y; w-1; h-1; tint R; tint GB),
upload op = 0x2xxx with dx, dy, w-1, h-1 and the pixels inline. `bl_blitter_log.lua` logs both from power-on;
`map_uploads.py` maps the 19,834 uploads (256 × 5-row strips of 256-wide images, 512-byte stride) to 3,572 rectangles
in the ROM (all found). The select screen runs ~830-890 draw ops a frame (most are 32 × 32 background tiles); 940
distinct source rectangles over 267 logged frames; 333,120 ROM-backed blitter pixels sampled (~650 KB as 16-bit,
~10 of our 256 × 128 pages) plus 113,920 frame-buffer pixels (x 960-1315, y 136-455: copy effects, not ROM art).
