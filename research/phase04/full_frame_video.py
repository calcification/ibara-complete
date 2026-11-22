"""Experimental 240-active-line NTSC Tate profile for SLPM-66301."""

# PSMCT32 uses 64x32 pages. At 640 pixels wide, a 224-line buffer is 70 pages,
# and a 240-line buffer is 80. Keep the two output buffers, the composition
# target and the depth buffer disjoint. The composition scissor stops at 383
# so it fits in pages 160–279 while still covering the 240x320 source image.
FULL_FRAME_EDITS = [
    (0x001B9CF0, 0x240601C0, 0x240601E0),  # Boot geometry: 448 -> 480 before progressive height is halved.
    (0x0014779C, 0x24630019, 0x24630011),  # NTSC progressive DISPLAY start: 25 -> 17 to center +16 lines.
    (0x0010E740, 0x3C0243E0, 0x3C0243F0),  # Tate R output height (480 half-lines).
    (0x0010E844, 0x3C0243E0, 0x3C0243F0),  # Tate L output height.
    (0x0010E71C, 0x3C024000, 0x3C020000),  # Tate R: exactly 640 pixels across, without the +/- 2 px overscan.
    (0x0010E830, 0x3C024000, 0x3C020000),  # Tate L: same 2x horizontal scale.
    (0x001AEA6C, 0x240200DF, 0x240200EF),  # Final-pass SCISSOR, including the screen-adjust path.
    (0x001AEA78, 0x240600DF, 0x240600EF),
    (0x001B28D8, 0x3C0200DF, 0x3C0200EF),
    (0x001AF380, 0x24060046, 0x24060050),  # Second output buffer, also used for temporary texture uploads.
    (0x001BB060, 0x240408C0, 0x24040A00),
    (0x001AF080, 0x24051180, 0x24051400),  # Composition texture base for both field packet variants.
    (0x001AF0B4, 0x24051180, 0x24051400),
    (0x001C5BC4, 0x24051180, 0x24051400),  # Composition uploads.
    (0x001C5C74, 0x3C020004, 0x3C020005),  # Stage background and effects use the same composition target.
    (0x001C5C7C, 0x34516000, 0x34510000),
    (0x001C5EE8, 0x3C020004, 0x3C020005),
    (0x001C5EEC, 0x34516000, 0x34510000),
    (0x001C64E8, 0x3C020004, 0x3C020005),
    (0x001C64EC, 0x34506000, 0x34500000),
    (0x001C5C90, 0x34423000, 0x34428000),  # Temporary output-buffer texture and readback destinations.
    (0x001C5CB0, 0x34423000, 0x34428000),
    (0x001C6444, 0x34633000, 0x34638000),
    (0x001C6A30, 0x34633000, 0x34638000),
    (0x001C5F24, 0x3C0301BF, 0x3C03017F),  # Composition SCISSOR sends the same limit in generated packets.
    (0x001C6524, 0x3C0301BF, 0x3C03017F),
]

# FRAME and SCISSOR words in the prebuilt GS packets. Audio and game logic are unaffected.
FULL_FRAME_EDITS += [(a, 0x000A0046, 0x000A0050) for a in (0x002A8A70, 0x002A8CB0, 0x002A8D70)]
FULL_FRAME_EDITS += [(a, 0x000A008C, 0x000A00A0) for a in (0x002A8C70, 0x002A8D30, 0x00301290)]
FULL_FRAME_EDITS += [(a, 0x01BF0000, 0x017F0000) for a in (0x002A8C84, 0x002A8D44, 0x003012A4)]
FULL_FRAME_EDITS += [(a, 0x00DF0000, 0x00EF0000) for a in (
    0x002A85D4, 0x002A8614, 0x002A8CC4, 0x002A8D04, 0x002A8D84, 0x002A8DC4, 0x00300E14,
)]

# Lower-right corner of each 64-pixel-wide strip in the output clear packet.
# The upper edge stays at the existing drawing origin, 0x7900 (1936 in GS pixels).
CLEAR_CORNERS = (0x002A8648, 0x002A8658, 0x002A8668, 0x002A8678, 0x002A8688,
                 0x002A8698, 0x002A86A8, 0x002A86C8, 0x002A86D8, 0x002A86E8)
FULL_FRAME_EDITS += [(a, 0x87007000 + i * 0x400, 0x88007000 + i * 0x400)
                     for i, a in enumerate(CLEAR_CORNERS)]
