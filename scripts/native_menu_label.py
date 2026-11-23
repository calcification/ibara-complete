"""Compose NOIR MODE from the retail Mode Select atlas, using only disc offsets."""

import struct


LABEL = "NOIR MODE"
LABEL_BOX = (112, 192, 224, 208)
ATLAS_WIDTH = 256
ATLAS_PDM_OFFSET = 0x2D20800  # IBARAR.PDM resource 945

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


def atlas_layout(iso, pdm_start):
    """Return the retail atlas's index offset and palette type."""
    offset = pdm_start + ATLAS_PDM_OFFSET
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
