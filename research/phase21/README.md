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

The same routine also draws the XTC number next to the ship (green `0x30F060`, flashing white for its first frames,
fading over the 128-frame timer; digit sprites `0C175418` / `0C1754B4`) and, while player +0x289 is set, a
rank-coloured glow (`0C1752A8`, colours as the RANK bar). Both are not ported yet; +0x289 stayed 0 in this capture.

## PS2 (KURO, with `--bl-rom`)

`bl_sphere()` in `ps2/hooks/bl_rankbar.c`, from the HUD pass, through the RANK bar's texture object: the 16 frames
sit on page 5 row 96 (frame f at column 16 f), placed there by the patcher from the atlas
(`research/phase20/make_select_data.py` adds them and checks the select art stays clear of those rows). Held
frames = `xtc.c`'s counter (the same 0..8 count). PCSX2: the orb turns on the ship while Cross is held and
disappears on release; side by side with a MAME snapshot it sits at the same place.
