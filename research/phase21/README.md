# Phase 21 — the XTC graze sphere (2026-11-22)

## What Black Label draws (`0C071110`, the block at `0C071380`)

While a player holds the shot, BL draws a small orb on the ship: player +0x270 is the shot-held count (1..8 —
`bl_graze_log.lua`: it ramps 1, 2 … 8 one per frame after the button goes down and stays at 8), and the block runs
whenever it is non-zero.

* Sprite: one of 16 descriptors `0C1751C8[side * 8 + ((frame counter 0C2B039C >> 2) & 7)]`, each a 16 × 16
  sprite at offset (−8, −8) (ids `0x9800 + 16 f`): a rotating orb, blue for player 1, red for player 2. Blitter
  source (`0x1498`, `0x700 + 16 f`), 16 × 16; in the ROM inside the 256 × 256 rectangle mapped by phase 20
  (`patcher/bl_select_atlas.json`, rect (5120, 1792)).
* Position: player (+0x10, +0x14) + the ship kind's offset (`0C1754E0[kind]` → +2 px straight, −2 px spread along
  game x; 0 along y).
* Drawn twice, tint `0x808080`: flags `0x1217FF00` (attr 0x317, alpha 0xFF00), then `0x12040000 | held × 0x808`
  (attr 0x304, alpha 0x4040 at 8 frames). Captured draw ops (frame 900): two 8 × 16 halves per pass at blitter
  (0x1DC/0x1E4, 0xD8), exactly these flags.

## The XTC number popup (same routine, `0C071110`-`0C0712F2`)

* State (graze test `0C06EF50`): on every graze the quarter count +0x280 goes up; when the displayed value
  (+0x280 >> 2) changes, the timer +0x284 = 128 and the popup position +0x278 / +0x27C = the player's position.
  The graze also adds 10 points, **110 at stored rank 0** (`0C06F0CA`), and plays sound 89.
* Drawn while the value is non-zero: "+" then the digits. Value <= 999: 8 × 8 digits (`0C1754B4`, VRAM (0x6F0,
  0x80 + 8 d), "+" (0x6F0, 0x58)), offset (−8, −8); above 999: 16 × 16 (`0C175418`, VRAM (0x690, 16 d), "+" (0x6A0,
  0xB0)), offset (−16, −16). Anchor: x + 32 px + (128 − timer) × 0.25 px (it drifts), y + 8 slot + 4 (digits + 1) −
  40 (big: 16 slot + 8 (digits + 1) − 80), least significant digit in slot 5, "+" in the slot after the most
  significant one. Flags `0x12040000`, alpha min(2 timer, 192); tint `0x30F060`, `0xFFFFFF` on odd frames while
  timer > 119.
* Checked: forced values in MAME (`bl_graze_log.lua` variant writing +0x280 / +0x284 / +0x278 / +0x27C): the draw
  ops match the formulas for 120, 345, 678, 901, 1234, 5678, 9090.
* PS2: `bl_xtc_popup()` (`ps2/hooks/bl_rankbar.c`) from `xtc.c`'s counter, timer and the position it now records;
  digits on page 5 rows 112-127. PCSX2 with the test define `BL_TEST_XTC_POPUP` (one graze per frame from 990 while
  the shot is held): "+996" small, then "+1002" … big, green, fading out after release. `xtc.c` also gives 110 per
  graze at rank 0.

Not ported: the graze sound (BL sound 89; PS2 has no matching sound id located), and the rank-coloured glow drawn
while player +0x289 is set (`0C1752A8`; +0x289 is also required for a graze — very likely BL's "pods out", which
`xtc.c` still does not check, XTC_REQUIRE_PODS).

## PS2 (KURO, with `--bl-rom`)

`bl_sphere()` in `ps2/hooks/bl_rankbar.c`, from the HUD pass, through the RANK bar's texture object: the 16 frames
sit on page 5 row 96 (frame f at column 16 f), placed there by the patcher from the atlas
(`research/phase20/make_select_data.py` adds them and checks the select art stays clear of those rows). Held
frames = `xtc.c`'s counter (the same 0..8 count). PCSX2: the orb turns on the ship while Cross is held and
disappears on release; side by side with a MAME snapshot it sits at the same place.
