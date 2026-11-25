# Commissioned logo — specification (draft, 25 November 2026)

An original logo replaces the retail 鋳薔薇 logo as a drop-in: same textures, same places on screen. The title
artwork and everything else stay as on the disc. Because the logo is commissioned (not taken from the game or the
arcade ROM), it can be committed and shipped inside the patch — the contract with the artist must allow that.
The goal is a tiny patch: today's patch is 29 KB (already compressed; almost all of it is our code and the select
screen's tables), and the logo should add only a few KB.

## Where the logo is on the PS2 disc

| Use | Texture (resource archive `IBARAR.PDM`) | Notes |
|---|---|---|
| Title screen | entry **875**, 256 × 256, 8-bit indexed, one 256-colour palette (32-bit entries), alpha 0 or opaque only | texture table row 4 / col 13 while the title is up. The texture holds three things: rows 0–~80 a piece of the title's silhouette artwork (keep), rows ~84–136 the 鋳薔薇 kanji with small "I BA RA" letters (about 240 × 52), rows ~140–206 a large "IBARA" wordmark (about 205 × 66). The title draws the kanji line **magnified about 2×** with a blue outline (PCSX2 screenshots), so on-screen sharpness is limited by the texture's pixels. |
| Attract demo banner, high-score screens | entry **876**, 256 × 256, same format | small 鋳薔薇 / IBARA logos next to the "Today's Heroes / Heroes' Histories" banners; they share the texture's palette with those banners |
| Menus (Mode Select, ARCADE / ARRANGE / NOIR menus) | menu header plate, top right | texture not located yet |

**Still to pin down before the artist starts** (a GS-level capture of the title, attract and score screens): the exact
source rectangle and on-screen scale of each use, whether the large "IBARA" wordmark is drawn anywhere, whether the
title's draw blends partial alpha (if it does, soft edges become possible), and the menu plate's texture.

## What to ask the artist for

1. **A master** at any resolution (kept outside the repository) and **final-pixel versions** at the texture sizes:
   - the main logo line: about 240 × 52 (fits the kanji line's area; the title shows it ~2× larger),
   - optionally a wordmark line: about 205 × 66 (only if that line turns out to be used),
   - the small versions for entry 876 (sizes from the capture above); or let the patcher scale them from the main
     logo at no patch cost, and commission hand-made ones only if the scaled ones look poor.
2. **At most 16 flat colours** (32 at the very most). The patch stores indexed pixels with LZMA; measured on the
   retail logo area (240 × 123): 16 colours ≈ 5.3 KB, 64 colours ≈ 7.3 KB. A clean flat design compresses to ≈ 1–2 KB.
3. **Hard edges**, transparent background, no anti-aliasing against transparency (the texture has on / off
   transparency only, unless the capture shows the title blends partial alpha). Pixel-clean art reads best at 2×.
4. Readable when magnified ~2× (title) and at its small size (banners).
5. Delivered as indexed PNG files at the final sizes, plus the master.

## How it ships

* `patcher/art/` (to be added): the final-size indexed images, compressed (LZMA) or as PNG (decoded by the patcher
  with the standard library).
* The patcher writes the new pixels and palette entries into entries 875 / 876 (and the menu plate's texture) in
  place: only the logo's rectangles and the palette entries the old logo used change; the silhouette art and banners
  stay. The archive entries keep their size, so the disc does not grow.
* No `--bl-rom` needed for the logo.
