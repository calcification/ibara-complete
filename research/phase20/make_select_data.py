#!/usr/bin/env python3
"""Phase 20: Black Label (KURO) select screen data from the MAME captures (bl_select_capture.lua).

    python3 research/phase20/make_select_data.py CAP_S CAP_P CAP_FULL VRAM_MAP OUTDIR [--p2 CAP_S2 CAP_P2]
        [--emit ROOT] [--rom ibarablk_u2]

CAP_S / CAP_P: one-player captures choosing straight / spread (types A-D); CAP_FULL: the long capture (timer);
CAP_S2 / CAP_P2: two-player captures in which player 2 (started at frame 120) makes the same inputs at the same
frames as player 1 does in CAP_S / CAP_P (research/phase20/bl_select_capture_p2.lua);
VRAM_MAP: map_uploads.py output. Writes OUTDIR/select_scene.json (states -> draw ops, sprites -> blitter rects) and,
with --rom, preview PNGs of every state (local checks only; never commit them).

Stage one: one steady frame per state (no per-element animation, no transitions, no girder background).
"""
import json
import struct
import sys
from pathlib import Path

# (capture, frame) of each state; frames read off the captures' input schedule
SHIP = {"S": ("S", 199), "P": ("P", 395)}
TYPE = {("S", t): ("S", 455 + 50 * t) for t in range(4)}
TYPE.update({("P", t): ("P", 455 + 50 * t) for t in range(4)})
JOIN = ("S", 199)
HEAD = ("F", 150)
DIGIT_SRC = [(4584 if d < 5 else 4560, 1792 + 16 * (d % 5)) for d in range(10)]  # 24 x 16 each: 0-4, 5-9


def load(fn):
    frames, cur = {}, None
    for line in open(fn):
        line = line.strip()
        if line.startswith("F"):
            f = int(line.split()[1])
            cur = None if f in frames else f
            if cur is not None:
                frames[cur] = []
        elif line and cur is not None:
            v = line.split(",")
            frames[cur].append([int(v[0], 16), int(v[1], 16)] + [int(x) for x in v[2:8]] + [int(v[8], 16), int(v[9], 16)])
    return frames


def region(ops, name):
    if name == "HEAD":
        return [o for o in ops if o[4] >= 265]
    if name == "P1":
        return [o for o in ops if o[4] < 265 and o[5] < 120]
    return [o for o in ops if o[4] < 265 and o[5] >= 120]


def is_digit(o):
    return (o[2], o[3]) in {(4560, 1792 + 16 * k) for k in range(5)} | {(4576, 1792 + 16 * k) for k in range(5)} | \
        {(4584, 1792 + 16 * k) for k in range(5)}


def main(argv):
    cap_s, cap_p, cap_f, vmap, out = argv[:5]
    rom = argv[argv.index("--rom") + 1] if "--rom" in argv else None
    caps = {"S": load(cap_s), "P": load(cap_p), "F": load(cap_f)}
    p2 = "--p2" in argv
    if p2:
        i = argv.index("--p2")
        caps["S2"], caps["P2"] = load(argv[i + 1]), load(argv[i + 2])
    # header: the ops identical in every state (bar, 武機選択, timer box); the digits are drawn from the timer
    ref = [caps[c][f] for c, f in list(SHIP.values()) + list(TYPE.values())] + [caps[HEAD[0]][HEAD[1]]]
    common = set(map(tuple, ref[0]))
    for ops in ref[1:]:
        common &= set(map(tuple, ops))
    head = [o for o in caps[HEAD[0]][HEAD[1]] if tuple(o) in common and o[4] >= 200 and not is_digit(o)]
    hset = set(map(tuple, head))

    def region(ops, name):
        ops = [o for o in ops if tuple(o) not in hset and not is_digit(o)]
        return [o for o in ops if o[5] < 120] if name == "P1" else [o for o in ops if o[5] >= 120]
    states = {}
    for k, (c, f) in SHIP.items():
        states[f"ship_{k}"] = region(caps[c][f], "P1")
    for (k, t), (c, f) in TYPE.items():
        states[f"type_{k}{'ABCD'[t]}"] = region(caps[c][f], "P1")
    states["join_P2"] = region(caps[JOIN[0]][JOIN[1]], "P2")
    if p2:  # player 2's panel (screen half y >= 120) at the frames of player 1's states
        for k, (c, f) in SHIP.items():
            states[f"ship_{k}2"] = region(caps[c + "2"][f], "P2")
        for (k, t), (c, f) in TYPE.items():
            states[f"type_{k}2{'ABCD'[t]}"] = region(caps[c + "2"][f], "P2")
    states["head"] = head
    digit_op = [o for o in caps[HEAD[0]][HEAD[1]] if is_digit(o)][0]
    sprites = {}
    for ops in states.values():
        for o in ops:
            sprites.setdefault((o[2], o[3], o[6], o[7]), len(sprites))
    for d in range(10):
        sprites.setdefault((DIGIT_SRC[d][0], DIGIT_SRC[d][1], 24, 16), len(sprites))
    scene = {
        "states": {n: [[o[0], o[1], sprites[(o[2], o[3], o[6], o[7])], o[4], o[5], o[8], o[9]] for o in ops]
                   for n, ops in states.items()},
        "digits": [sprites[(DIGIT_SRC[d][0], DIGIT_SRC[d][1], 24, 16)] for d in range(10)],
        "digit_op": [digit_op[0], digit_op[1], digit_op[8], digit_op[9]],
        "digit_pos": [[280, 192], [280, 208]],
        "sprites": [list(k) for k, _ in sorted(sprites.items(), key=lambda kv: kv[1])],
    }
    Path(out).mkdir(parents=True, exist_ok=True)
    Path(out, "select_scene.json").write_text(json.dumps(scene))
    if "--emit" in argv:
        emit(scene, json.load(open(vmap)), Path(argv[argv.index("--emit") + 1]))
    px = sum(w * h for _sx, _sy, w, h in scene["sprites"])
    print(f"{len(states)} states, {sum(len(v) for v in states.values())} ops, {len(sprites)} sprites, {px} px")
    if rom:
        preview(scene, json.load(open(vmap)), open(rom, "rb").read(), out)


# --- atlas and generated files ---------------------------------------------------------------------------------
PAGES, PAGE_W, PAGE_H = 8, 256, 128
RESERVED = (5, 20)  # page 5 rows 0-19: the rank bar (bl_rankbar.c)
SPHERE_PAGE, SPHERE_ROW, SPHERE_SX, SPHERE_SY = 5, 96, 0x1498, 0x700  # graze sphere frames (bl_rankbar.c)
STATE_ORDER = ["head", "join_P2", "ship_S", "ship_P"] + [f"type_{k}{t}" for k in "SP" for t in "ABCD"] + \
    ["ship_S2", "ship_P2"] + [f"type_{k}2{t}" for k in "SP" for t in "ABCD"]


def pack(sprites):
    """Skyline-pack sprites in screen orientation (pw = blitter h, ph = blitter w) into 256 x 128 pages."""
    order = sorted(range(len(sprites)), key=lambda i: (-sprites[i][2], -sprites[i][3]))
    sky = [[RESERVED[1] if pg == RESERVED[0] else 0] * PAGE_W for pg in range(PAGES)]
    place = [None] * len(sprites)
    for i in order:
        pw, ph = sprites[i][3], sprites[i][2]
        best = None
        for pg in range(PAGES):
            col = sky[pg]
            for x in range(0, PAGE_W - pw + 1):
                y = max(col[x:x + pw])
                limit = SPHERE_ROW if pg == SPHERE_PAGE else PAGE_H  # page 5 rows 96-127: sphere and XTC digits
                if y + ph <= limit and (best is None or (y, pg) < (best[0], best[2])):
                    best = (y, x, pg)
            if best is not None and best[2] == pg:
                break
        if best is None:
            raise SystemExit("select art does not fit the texture pages")
        y, x, pg = best
        place[i] = (pg, x, y)
        for c in range(x, x + pw):
            sky[pg][c] = y + ph
    return place


def flags_of(attr, alpha):
    return (0x10000000 | (attr & 0x277) << 16 | (0x08000000 if attr & 0x800 else 0) |
            (0x04000000 if attr & 0x400 else 0) | alpha)


def emit(scene, vmap, root):
    sprites = scene["sprites"]
    place = pack(sprites)
    lines = ["/* GENERATED by research/phase20/make_select_data.py from MAME captures of Black Label's select screen:",
             " * coordinates, sizes, blend flags and tints only (the pixels come from the user's ROM through the",
             " * patcher's atlas, patcher/bl_select_atlas.json). Do not edit. */",
             '#include "ibara_ps2.h"', '#include "bl_select.h"', "",
             "const struct sel_sprite sel_sprites[%d] = {" % len(sprites)]
    for (sx, sy, w, h), (pg, x, y) in zip(sprites, place):
        lines.append("\t{%d, %d, %d, %d, %d}, /* blitter %d,%d %dx%d */" % (pg, x, y, h, w, sx, sy, w, h))
    lines.append("};")
    ops, first = [], []
    for name in STATE_ORDER:
        if name not in scene["states"]:
            continue
        first.append(len(ops))
        ops += scene["states"][name]
    first.append(len(ops))
    lines.append("const struct sel_op sel_ops[%d] = {" % len(ops))
    for attr, alpha, si, x, y, tr, tgb in ops:
        lines.append("\t{%d, %d, %d, 0x%08Xu, 0x%06Xu}," % (si, x, y, flags_of(attr, alpha), (tr & 0xFF) << 16 | tgb))
    lines.append("};")
    lines.append("const u16 sel_state_first[%d] = {%s};" % (len(first), ", ".join(map(str, first))))
    a, al, tr, tgb = scene["digit_op"]
    lines.append("const u8 sel_digit_sprite[10] = {%s};" % ", ".join(map(str, scene["digits"])))
    lines.append("const u32 sel_digit_flags = 0x%08Xu, sel_digit_tint = 0x%06Xu;" % (flags_of(a, al), (tr & 0xFF) << 16 | tgb))
    (root / "ps2/hooks/bl_select_data.c").write_text("\n".join(lines) + "\n")
    # the XTC graze sphere's 16 frames (research/phase21; drawn with the RANK bar's texture object, page 5):
    # blitter (0x1498, 0x700 + 16 f) 16 x 16 -> page 5 row 96, column 16 f
    extra = [(SPHERE_SX, SPHERE_SY + 16 * f, 16, 16) for f in range(16)]
    # the XTC number popup's digits (research/phase21): big 0-9 + '+' at page 5 rows 112-127, columns 16 d; small
    # 0-9 at rows 112-119, columns 176 + 8 d, small '+' at row 120, column 176
    xtc = [((0x690, 16 * d) if d < 10 else (0x6A0, 0xB0)) + (16, 16, SPHERE_PAGE, 16 * d, 112) for d in range(11)] + \
          [(0x6F0, 0x80 + 8 * d if d < 10 else 0x58, 8, 8, SPHERE_PAGE, 176 + 8 * d if d < 10 else 176,
            112 if d < 10 else 120) for d in range(11)]
    for (sx, sy, w, h), (pg, x, y) in zip(sprites, place):
        if pg == SPHERE_PAGE and y < 128 and SPHERE_ROW < y + w:
            raise SystemExit("select art overlaps the graze sphere / XTC digit rows (page 5 rows 96-127)")
    used = []
    for i, (dx, dy, w, h, off) in enumerate(vmap):
        if any(dx < sx + sw and sx < dx + w and dy < sy + sh and sy < dy + h for sx, sy, sw, sh in sprites + extra + [x[:4] for x in xtc]):
            used.append([dx, dy, w, h, off])
    atlas = {"note": "Black Label select screen atlas: sprite = [blitter x, y, w, h, page, page x, page y] (screen "
                     "orientation: page pixel (row i, col j) = blitter (x + w - 1 - i, y + j)); rects = blitter "
                     "uploads [x, y, w, h, ibarablk_u2 offset], later ones win. Coordinates only.",
             "sprites": [list(s) + list(p) for s, p in zip(sprites, place)] +
                        [list(e) + [SPHERE_PAGE, 16 * f, SPHERE_ROW] for f, e in enumerate(extra)] +
                        [list(x) for x in xtc], "rects": used}
    (root / "patcher/bl_select_atlas.json").write_text(json.dumps(atlas, separators=(",", ":")) + "\n")
    print(f"atlas: {max(p[0] for p in place) + 1} pages, {len(used)} upload rects; {len(ops)} ops")


def vram_pixel_fn(vmap, raw):
    """(x, y) -> 16-bit pixel of the blitter memory as last uploaded (later uploads win)."""
    import numpy as np
    owner = {}
    for i, (dx, dy, w, h, off) in enumerate(vmap):
        for by in range(dy // 8, (dy + h + 7) // 8):
            for bx in range(dx // 256, (dx + w + 255) // 256):
                owner.setdefault((bx, by), []).append(i)

    def px(x, y):
        for i in reversed(owner.get((x // 256, y // 8), [])):
            dx, dy, w, h, off = vmap[i]
            if dx <= x < dx + w and dy <= y < dy + h:
                return struct.unpack_from(">H", raw, off + ((y - dy) * w + (x - dx)) * 2)[0]
        return 0
    return px


def preview(scene, vmap, raw, out):
    import numpy as np
    from PIL import Image
    px = vram_pixel_fn(vmap, raw)
    cache = {}

    def sprite(i):
        if i not in cache:
            sx, sy, w, h = scene["sprites"][i]
            cache[i] = np.array([[px(sx + x, sy + y) for x in range(w)] for y in range(h)], np.uint32)
        return cache[i]

    def draw(img, op):
        attr, alpha, si, x, y, tr, tgb = op
        a = sprite(si)
        h, w = a.shape
        sa = ((alpha >> 8) & 0xFF) / 255.0
        tint = np.array([tr & 0xFF, tgb >> 8, tgb & 0xFF]) / 128.0
        for yy in range(h):
            for xx in range(w):
                p = int(a[yy, xx])
                if attr & 0x100 and not p & 0x8000:
                    continue
                c = np.array([(p >> 10) & 31, (p >> 5) & 31, p & 31]) * 8.0 * tint
                gx, gy = x + xx, y + yy  # landscape game coords; screen: col = gy, row = 319 - gx
                if not (0 <= gx < 320 and 0 <= gy < 240):
                    continue
                d = img[319 - gx, gy]
                if attr & 0x200 and (attr & 7) == 7:
                    c = d + c * sa
                elif attr & 0x200:
                    c = c * sa + d * (1 - sa)
                img[319 - gx, gy] = np.clip(c, 0, 255)

    for name, ops in scene["states"].items():
        img = np.zeros((320, 240, 3))
        for op in scene["states"]["head"] + (ops if name != "head" else []):
            draw(img, op)
        for k, (dx, dy) in enumerate(scene["digit_pos"]):
            a, al, tr, tgb = scene["digit_op"]
            draw(img, [a, al, scene["digits"][[6, 0][k]], dx, dy, tr, tgb])
        Image.fromarray(img.astype("uint8")).save(Path(out, f"preview_{name}.png"))


if __name__ == "__main__":
    main(sys.argv[1:])
