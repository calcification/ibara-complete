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

## Findings for the PS2 port (2026-11-22)

**Coordinates.** The blitter double-buffers at scroll x 32 / 416 (register `0x18000014`), y origin 136: game
coordinates = dst − (buffer x, 136); landscape, game x up the portrait screen. PS2 keeps the same system: its HUD
offsets are x 416 / y 136 (`$gp-28648` / `$gp-28640`), so a BL draw op maps onto `0x00110B70` directly:
x = dst_x − origin + 416, y = dst_y − 136 + 136; w (along x) = op w, h (along y) = op h; texture = the source rect
in a page of ours (screen orientation: pixel (row i, col j) = blitter (sx + w − 1 − i, sy + j)); tint = R << 16 |
GB (0x80 = 1.0, same as PS2); a0 = 0x10000000 | (attr & 0x277) << 16 (blend bit, s_mode, d_mode — PS2 tests the
same d_mode 7 / s_mode 1 values at `0x00110DCC`; Arrange's gauge uses blend + d_mode 4 = 0x2040000) | flipx →
0x08000000, flipy → 0x04000000 | alpha word (s_alpha << 8 | d_alpha, as PS2).

**Screen contents per frame** (≈ 830-890 ops): 414 32 × 32 tiles compose the girder background off-screen
(blitter x 960-1315, y 136-455), copied to the screen one 1-px row at a time with a per-row x offset (a heat-shimmer
wave) and tint 0x58 (dark); ~80-100 element ops (header 武機選択 at game x 272-311, timer, the two side panels at
y < 120 / ≥ 120, portraits, ship renders, name plates, the join panel, prompt, 8 × 8 font text for CREDIT / PRESS
START). Steady state: ~10 ops animate (pulsing / blinking); a ship change plays ~30 frames of moving ops (fly-in);
P2 joining switches that panel.

**Sizes.** Element art (everything but the background tiles and the frame-buffer copies): 150 distinct source
rects, 179,520 pixels = 5.5 pages of 256 × 128 PSMCT16 (fits the 6-page area at `0x01F20000`); the background adds
the tile set (stage 2 of option 3).

**Holding the game while the screen is up.** The main loop (`0x0012E1E4`) skips the game update while the pause
byte `$gp-28128` is set and then calls the pause menu `0x00128E10` (`jal` at `0x0012E778`; returns 0 = stay, 3 =
restart / title); the HUD pass (and our sprites) still render. KURO plan: set the byte at the start of a KURO game,
replace that call with the select screen's own (draws, reads the pad, returns 0), then write the ship word / FIGHTER
TYPE config and clear the byte.

**Art delivery plan.** Pages pre-laid-out by the patcher from the user's ROM (vram_map offsets + an atlas layout,
both coordinates only) into an extra loadable segment of the frontend executable at `0x01F20000` (zeros on the
disc without `--bl-rom`; the executable's disc extent has ample free space, the ISO size is unchanged).

## The select flow (captures, 2026-11-22)

`bl_select_capture.lua` (one player; Right / Left, button, Down ×4, Up, button):

1. **Ship:** left / right picks straight (シスター・シミリス, 直進型) or spread (ディオ・スピロッソ, 拡散型); a fly-in
   transition (~30 frames) on each change; prompt 左右で機体を選択.
2. **Type:** the button opens TYPE A / B / C / D (up / down; prompt 上下でカスタムタイプ選択) with SPEED / POWER bars and
   the bomb kind (拡散 / 爆発 / 直進 / 全方位 ...) — BL chooses the type here, not in a settings menu.
3. **Confirm:** the button flashes the ship; the panels dissolve into the girder background, the ship launches, a
   pilot illustration plays, then stage 1.

The free side shows the 参戦可能 / PRESS START join panel; with two players each side runs the same two steps.
Per frame the P1 panel is ~40-50 ops; steady states have no single loop period (several independent animations:
pulsing highlights, blinking text, bobbing arrows), so the PS2 version will animate elements individually rather than
replay frame lists.
