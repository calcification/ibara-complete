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
  palette unchanged; the user chose palette-matched art over a separate 16-bit texture.

## KURO implementation (`ps2/hooks/bl_rankbar.c`, K28)

* The HUD pass's `jal 0x00129360` (`0x0012E42C`) calls `bl_rank_bar` in KURO (a KURO table word). Without art it
  calls the Arrange gauge, as before.
* Art: `bl_bar_blob` (tag `BLRANKBAR-ART-01` + 80 × 14 big-endian words) is zero in the repository and in the patch;
  `patcher/apply_kuro_patch.py --bl-rom` / `scripts/build_black_label_iso.py --bl-rom` copy it from the user's
  `ibarablk_u2` (size and CRC checked) after the disc is verified. Patch + ROM gives a disc byte-identical to the
  direct build with the ROM.
* Painting: each colour → nearest entry of the page's CLUT (CSM1 order, weighted RGB distance); frame (80 × 6),
  plate (41 × 8) and a 70 × 2 grey fill strip go over Arrange's own gauge art (page x 0-127, y 160-171), saved first
  and put back when KURO switches off. Fully transparent rows are *not* free: painting rows 195-196 showed a
  coloured box over the 1P score (a1 = 828 sprites stretch texels from there).
* Drawing: three `0x00110B70` sprites (frame, plate, fill) through `bar_sprite`, which loads x, y, w, h into
  f12-f15 (our code is o32 soft-float). BL geometry: y 80-159 (centred), fill art x 5, rows 2-3, length and colours
  as above (GS modulate: tint = t × 128 / 124), rank-0 flash (tint `0xFFFFFF` on `$gp-28692` bit 1), proximity fade
  (flags `0x10000000 | 0x2040000 | a << 8 | a`), slide 16 px while `$gp-29064` is set. x = 301: PS2's high-score
  line sits higher than the arcade's, 9 px more puts the bar right under it. PS2's stage name (HUD text row 37,
  cols 5-18) is blanked in KURO while the bar shows (BL has none there).
* The file is built without s-registers (LEAF_SOURCES): the first version used them and the HUD pass that calls it
  keeps 128-bit values in s-registers, so the o32 32-bit save/restore corrupted its later sprites (a box of HUD
  texture over the 1P score).

PCSX2 (K28): KURO game: frame, blue fill at low rank, RANK plate centred under TOP; no box over the 1P score; after a
KURO Game Over (KURO off) a plain Arcade game shows Arrange's gauge art intact. `make_patch.py` literal-run limit
4 → 8 KiB (our hook image is one ~6.5 KB run).

