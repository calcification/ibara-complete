#!/usr/bin/env python3
"""Phase 20: map Black Label blitter uploads (bl_blitter_log.lua's U lines) to offsets in the user's ibarablk_u2.

    python3 research/phase20/map_uploads.py uploads.txt ibarablk_u2 vram_map.json

uploads.txt: `U dx dy w h ram frame binoffset` lines with the strips' pixels in uploads.txt.bin (bl_upload_log.lua).
Each strip's full pixel data is found in the ROM (first the bytes after the previous strip: strips of one image
follow each other; else a search), so every mapped pixel is exact; strips are merged into rectangles (dx, dy, w, h,
rom offset). The output holds coordinates and offsets only, no pixels. (Matching only a 64-byte head mapped mostly
blank first strips to the wrong place.)
"""
import json
import sys


def main(log, rom, out):
    raw = open(rom, "rb").read()
    blob = open(log + ".bin", "rb").read()
    recs = []
    for line in open(log):
        p = line.split()
        if p and p[0] == "U":
            dx, dy, w, h, at = int(p[1]), int(p[2]), int(p[3]), int(p[4]), int(p[7])
            recs.append((dx, dy, w, h, blob[at:at + w * h * 2]))
    rects, prev, miss = [], None, 0
    for dx, dy, w, h, data in recs:
        off = prev if prev is not None and raw[prev:prev + len(data)] == data else raw.find(data)
        if off < 0:
            miss += 1
            prev = None
            continue
        prev = off + w * h * 2
        r = rects[-1] if rects else None
        if r and r[0] == dx and r[2] == w and r[1] + r[3] == dy and r[4] + r[2] * r[3] * 2 == off:
            rects[-1] = (r[0], r[1], r[2], r[3] + h, r[4])
        else:
            rects.append((dx, dy, w, h, off))
    json.dump(rects, open(out, "w"))
    print(f"{len(recs)} uploads, {miss} not found, {len(rects)} rectangles")


if __name__ == "__main__":
    main(*sys.argv[1:4])
