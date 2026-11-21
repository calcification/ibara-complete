# Phase 19 — Black Label's centred RANK bar (2026-11-21)

## What BL draws (`0C0703C0`, BL-only, every frame)

MAME snapshots (`snap*.lua` variants of `tools/stage_compare/bl_bomb_probe.lua`'s start-up) and the routine:

* Art: one 80 × 14 sprite (screen orientation) centred under the high score: a 6-px metal frame (rows 0-5) and the
  8-px "RANK" plate under it (rows 6-13), 133 colours, drawn from sprite IDs `0x369/0x36E/0x36F` (list
  `0C174FA4`) with tint `0x808080` (identity).
* Fill: inline sprite (`0C174FC0` → `0C174FAC/0C174FB6`) at art x = 5, rows 2-3, length
  `((0xFFFFFF - rank) >> 8) * 70 >> 16` px (69 max unless rank = 0, then 70), texture rows 2/3 = grey 23/13 (5-bit),
  tinted with L = (0xFFFFFF - rank) >> 16: R = max(0, 2L - 255), G = 2L ≤ 255 ? 2L : 510 - 2L, B = max(0, 255 - 2L).
  Blitter tint: out = min(31, src × (t >> 2) / 31). Model checked on every fill pixel at 13 rank values.
* Rank 0: the bar is drawn with tint `0xFFFFFF` on alternate beats (`0C2B039C & 2`).
* Fade: when a player is within the bar's box, alpha = ((|dy| - 48, ≥ 0) + |dx|) × 8 (max over players, ≤ 255).
* Position slides 1 px / frame to x target `0x124`, `0x114` while `0C3CC308` ≠ 0.

## Where the art is in the user's ROM (`ibarablk_u2`, 138,412,032 bytes, CRC 5e46be44)

Raw, uncompressed, big-endian 16-bit (bit 15 = opaque, then 5:5:5 RGB), laid out in the blitter's landscape
orientation: screen pixel (x, y) of the 80 × 14 art = the word at **`0x06D269F0 + x × 512 − y × 2`** (an image 256
pixels wide; the NAND spare bytes are at the end of this dump, not interleaved). Found by searching the ROM for screen
columns (rows failed: the game is vertical); all 1,120 pixels and their transparency match the MAME output exactly.
Only these offsets go in the repository; the patcher will read the pixels from the user's own ROM.

## PS2 side

* PS2's Arrange gauge `0x00129360` is a port of the same routine (slide target 290 / −16, the proximity fade, the
  rank-0 flash with `0xFFFFFF`, the 2L − 255 colours) with Arrange's own art (top right, a 12 × 120 texture at u/v
  852/256), drawn by `0x00110B70` (a0 = flags/alpha, a1/a2 = texture page·256 + u / v, f12-f15 = x, y, w, h).
* Textures are objects (`0x00341780` page table → `0x00339DB0` objects); the HUD page is a TIM2 in EE RAM
  (`0x00984E00`, 256 × 256 PSMT8, 256-entry CLUT, **all 256 entries used**), uploaded by its object's DMA packets
  (`obj+36` → `0x009A57C0` image, `0x009A58C0` CLUT) when drawn. So the 133-colour art cannot go into that page's
  palette; it needs its own 16-bit texture (an object of ours with its own upload packets) — open.
