"""Compose the NOIR MODE row and header from original menu texture indices."""

import struct


LABEL = "NOIR MODE"
LABEL_BOX = (112, 192, 224, 208)
ATLAS_WIDTH = 256
ATLAS_PDM_OFFSET = 0x2D20800  # IBARAR.PDM resource 945
HEADER_PDM_OFFSET = 0x2D31000  # Resource 946, texture 3
HEADER_BOX = (112, 96, 224, 144)
HEADER_UV = (ATLAS_WIDTH - HEADER_BOX[3]) << 24 | HEADER_BOX[0] << 16 | 3

# Source row, source x at the glyph origin, destination x within LABEL_BOX,
# then one (left, right) source span per row. The varying edges keep adjoining
# glyphs' shadows out of each cut. N and O are from OPTION, I from EXIT,
# R from GALLERY, and MODE from ARCADE MODE.
GLYPHS = (
    (112, 56, 0, tuple(zip(
        (58, 58, 59, 59, 59, 59, 58, 58, 58, 58, 58, 58, 57, 56, 56),
        (73, 74, 74, 73, 73, 73, 72, 72, 72, 72, 72, 72, 72, 71, 71),
    ))),
    (112, 0, 16, tuple(zip(
        (5, 3, 2, 2, 1, 1, 0, 0, 0, 0, 1, 1, 2, 3, 4),
        (12, 12, 13, 14, 14, 14, 14, 14, 14, 14, 13, 13, 12, 11, 11),
    ))),
    (112, 107, 29, tuple(zip(
        (109, 109, 110, 110, 110, 110, 110, 109, 109, 109, 109, 109, 108, 107, 107),
        (118, 117, 116, 116, 116, 116, 116, 116, 116, 116, 115, 115, 115, 116, 116),
    ))),
    (96, 58, 39, tuple(zip(
        (60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 59, 58, 59),
        (72, 72, 72, 71, 71, 71, 71, 71, 71, 71, 71, 71, 73, 73, 73),
    ))),
    (64, 68, 56, ((68, 112),) * 15),
)


def atlas_layout(iso, offset):
    """Return the index offset and palette type for a menu atlas at this ISO offset."""
    iso.seek(offset)
    header = iso.read(16)
    if len(header) != 16 or header[:4] != b"TIM2":
        raise ValueError("Unexpected magic for menu label atlas")
    picture = offset + (128 if header[5] else 16)
    iso.seek(picture)
    fields = struct.unpack("<IIIHHBBBBHH", iso.read(24))
    _, palette_size, pixel_size, header_size, _, _, _, palette_type, image_type, width, height = fields
    if (palette_size, pixel_size, palette_type & 0x1F, image_type, width, height) != (1024, 65536, 3, 5, 256, 256):
        raise ValueError("Unexpected menu label atlas layout")
    return picture + header_size, palette_type


def read_atlas(iso, offset):
    pixels, palette_type = atlas_layout(iso, offset)
    iso.seek(pixels)
    return pixels, iso.read(ATLAS_WIDTH ** 2), iso.read(1024), palette_type


def copy_spans(pixels):
    """Yield (destination, source, length) in texture or disc byte coordinates."""
    left, top, _, _ = LABEL_BOX
    for row in range(15):
        for source_y, origin, target_x, spans in GLYPHS:
            start, end = spans[row]
            yield (
                pixels + (top + row) * ATLAS_WIDTH + left + target_x + start - origin,
                pixels + (source_y + row) * ATLAS_WIDTH + start,
                end - start,
            )


# Blue header glyph cuts from OPTION (N, O), EXIT (I), GALLERY (R), and
# ARCADE MODE (MODE). Resize the wider letters horizontally to fit the plaque.
# Each cut specifies source x/y/width, destination x/width, and source x limits
# per row where neighboring outlines touch.
HEADER_GLYPHS = (
    (186, 48, 19, 16, 14,
     (189, 189, 189, 189, 189, 189, 189, 189, 189, 189, 189, 188, 188, 188, 188, 188, 187, 186, 186, 187),
     (205,) * 20),
    (128, 48, 15, 31, 12,
     (128,) * 20,
     (141, 141, 142, 143, 143, 143, 143, 143, 143, 143, 143, 143, 143, 143, 143, 142, 142, 141, 141, 139)),
    (53, 96, 12, 44, 8,
     (54, 54, 54, 54, 55, 55, 55, 55, 55, 55, 55, 55, 55, 55, 55, 54, 54, 53, 53, 53),
     (64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 63, 63, 63, 63)),
    (68, 48, 15, 53, 11,
     (70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 69, 68, 68, 68),
     (83, 83, 83, 83, 83, 83, 83, 83, 83, 83, 82, 82, 82, 82, 82, 82, 82, 83, 83, 83)),
    (64, 0, 35, 65, 35, (64,) * 20, (99,) * 20),
)


def header_spans(pixels, indices, clut, palette_type):
    """Map every pixel of the new plaque to a source byte in the same atlas."""
    def ink_color(index):
        if not palette_type & 0x80:  # GS CSM1 palette swaps bit 3 and bit 4.
            index = (index & ~0x18) | (index & 8) << 1 | (index & 16) >> 1
        r, g, b, a = clut[index * 4:index * 4 + 4]
        return a and (min(r, g, b) >= 218 or (b - r >= 27 and b - g >= 11))

    ink = {i for i in range(256) if ink_color(i)}
    left, top, right, bottom = HEADER_BOX
    width, height = right - left, bottom - top
    exit_top = 96
    plaque = [[(exit_top + y) * ATLAS_WIDTH + x for x in range(width)] for y in range(height)]
    # Restore the center of EXIT's plate with bare metal from the same plate.
    # Feather between the dark left bevel and the open metal to its right.
    for y in range(11, 37):
        for x in range(16, 83):
            from_bevel = (x * 13 + y * 7) % 23 > x - 14
            source_x = 12 + (x + y) % 3 if from_bevel else 83 + abs(x % 28 - 14)
            plaque[y][x] = (exit_top + y) * ATLAS_WIDTH + source_x

    glyphs = []
    for sx, sy, source_width, dx, dest_width, lo, hi in HEADER_GLYPHS:
        for row in range(20):
            y = row + 14
            for col in range(dest_width):
                x = sx + (2 * col + 1) * source_width // (2 * dest_width)
                offset = (sy + y) * ATLAS_WIDTH + x
                if lo[row] <= x < hi[row] and indices[offset] in ink:
                    glyphs.append((dx + col, y, offset))
    for x, y, _ in glyphs:
        for ox, oy in ((-1, 0), (1, 0), (0, 1), (1, 1), (0, 2)):
            # Shade from the pixels just beneath the original EXIT lettering.
            plaque[y + oy][x + ox] = (exit_top + (36 if oy == 2 else 35)) * ATLAS_WIDTH + 50
    for x, y, offset in glyphs:
        plaque[y][x] = offset

    for y, row in enumerate(plaque, top):
        dest = pixels + y * ATLAS_WIDTH + left
        start = 0
        for end in range(1, width + 1):
            if end == width or row[end] != row[start] + end - start:
                yield dest + start, pixels + row[start], end - start
                start = end
