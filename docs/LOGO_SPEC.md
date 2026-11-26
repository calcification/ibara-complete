# Commissioned logo — specification (draft, 25 November 2026)

An original logo replaces the retail 鋳薔薇 logo as a drop-in: same textures, same places on screen. The title
artwork and everything else stay as on the disc. Because the logo is commissioned (not taken from the game or the
arcade ROM), it can be committed and shipped inside the patch — the contract with the artist must allow that.
The goal is a tiny patch: today's patch is 29 KB (already compressed; almost all of it is our code and the select
screen's tables), and the logo should add only a few KB.

## Where the logo is on the PS2 disc

| Use | Texture (resource archive `IBARAR.PDM`) | Notes |
|---|---|---|
| Title screen | entry **875**, 256 × 256, 8-bit indexed, one 256-colour RGBA palette | The main draw samples **(0, 80) to (240, 168)**. A second draw samples **(0, 168) to (240, 224)**. Keep the silhouette area above row 80. |
| Attract and high-score banners | entry **876**, 256 × 256, same format | Small 鋳薔薇 / IBARA graphics share the palette with the “Today's Heroes / Heroes' Histories” banners. Banner draw rectangles and scale still need a live capture. |
| Mode Select header | entry **945**, 256 × 256, same format | The right header plate samples **(120, 0) to (240, 48)**, including the badge and its background. The left MODE SELECT plate uses **(0, 0) to (120, 64)**. |

## Verified draw geometry

Source rectangles use exclusive right and bottom edges. Output sizes below
are GS sprite dimensions before presentation scaling or user rotation.
The PCSX2 title dump used retail Yoko with a 640 × 448 display. The
compositor presented the 240-pixel game canvas as a 336-pixel-wide
centered image. Vertical presentation scaled the 320-pixel canvas to
about 478 pixels in the 640 × 480 PCSX2 screenshot.

| Draw | Source (left, top, right, bottom) | Sprite size | Sprite top-left |
|---|---|---:|---:|
| Title primary, TBP0 15000 | (0, 80, 240, 168) | 240 × 88 | (−0.5, 58.4375) |
| Title lower layer, TBP0 15000 | (0, 168, 240, 224) | 240 × 56 | (−0.5, 122.4375) |
| Mode Select left plate, TBP0 13960 | (0, 0, 120, 64) | 120 × 64 | (−0.5, −1.5625) |
| Mode Select right plate, TBP0 13960 | (120, 0, 240, 48) | 120 × 48 | (119.5, −1.5625) |

These draws use 1:1 GS sprite sizes. Presentation scales the title's
primary box to about 336 × 131 in the captured window. Within its source
box, the nontransparent pixels occupy **(1, 80) to (216, 168)**. The
lower layer contains glyphs from the large wordmark area at **(7, 168)
to (206, 207)**. It draws with an additive blend and vertex alpha 96.
The primary logo and Mode Select plates draw with standard source-alpha
blending and vertex alpha 128. Their alpha test accepts values greater
than 1. The draw can blend partial alpha. The current palettes of
entries 875, 876 and 945 contain only alpha 0 and 128. Soft edges would
require palette slots and a patcher check for the art sharing the palette.

The right plate's 120 × 48 is a placement box. Its background, border
and vine motif share that box with the logo badge. Supply a separate
transparent badge so the integrator can keep those details. The title's
two sprites use adjacent atlas rows and overlap by 24 GS pixels on
screen. Review both sprites together in the preview.

## What to ask the artist for

1. **A master** at any resolution (kept outside the repository) and **final-pixel versions** for the measured title
   boxes, 240 × 88 and 240 × 56, plus a compact badge for the 120 × 48 menu plate. Align the title designs with the
   existing visible bounds. Prepare the entry 876 versions after the banner draw is captured.
2. **At most 16 flat colours** (32 at the very most). The patch stores indexed pixels with LZMA; measured on the
   retail logo area (240 × 123): 16 colours ≈ 5.3 KB, 64 colours ≈ 7.3 KB. A clean flat design compresses to ≈ 1–2 KB.
3. **Hard edges** and a transparent background for the first production pass. Partial-alpha variants can be previewed
   if there is room in the shared palette.
4. Readable at the measured title scale and in the smaller menu badge.
5. Delivered as indexed PNG files at the final sizes, plus the master.

## How it ships

* `patcher/art/` (to be added): the final-size indexed images, compressed (LZMA) or as PNG (decoded by the patcher
  with the standard library).
* The patcher writes the new pixels and palette entries into entries 875 / 876 (and entry 945 for the menu plate) in
  place: only the logo's rectangles and the palette entries the old logo used change; the silhouette art and banners
  stay. The archive entries keep their size, so the disc does not grow.
* No `--bl-rom` needed for the logo.
