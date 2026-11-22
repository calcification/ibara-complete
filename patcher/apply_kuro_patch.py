#!/usr/bin/env python3
"""Ibara KURO patcher: turns your own 'Ibara (Japan).iso' (SLPM-66301) into the Ibara KURO disc.

    python3 apply_kuro_patch.py "Ibara (Japan).iso" "Ibara KURO.iso" [--bl-rom ibarablk.zip]

--bl-rom: your own Ibara Kuro Black Label arcade ROM set (MAME's ibarablk.zip, or its ibarablk_u2 file). The
centred RANK bar's artwork is copied from it into the new ISO; without it KURO shows Arrange's RANK gauge.

Windows: drag your ISO onto apply_kuro_patch.bat (or run: py apply_kuro_patch.py "Ibara (Japan).iso" out.iso).
Needs only Python 3.8+ (no extra packages) and ~3.7 GB of free disk space. Your ISO is only read.

The patch (ibara_kuro.patch, next to this script) holds this project's changes and copy instructions; every
game byte comes from your disc. The result is checked against the SHA-256 of the disc the patch was made from.
"""
import hashlib
import json
import shutil
import struct
import sys
import zipfile
import zlib
from pathlib import Path

MAGIC = b"IBKPATCH1\0"
HERE = Path(__file__).resolve().parent


def read_patch(path):
    raw = path.read_bytes()
    if not raw.startswith(MAGIC):
        raise SystemExit(f"{path} is not an Ibara KURO patch")
    body = zlib.decompress(raw[len(MAGIC):])
    src_size, dst_size = struct.unpack_from("<QQ", body, 0)
    src_md5, dst_sha = body[16:32].hex(), body[32:64].hex()
    p = 64
    n = body[p]
    note = body[p + 1:p + 1 + n].decode(errors="replace")
    p += 1 + n
    count, = struct.unpack_from("<I", body, p)
    p += 4
    records = []
    for _ in range(count):
        at, length, nops = struct.unpack_from("<QII", body, p)
        p += 16
        ops = []
        for _ in range(nops):
            kind = body[p]
            if kind == 0:
                src, ln = struct.unpack_from("<QI", body, p + 1)
                ops.append((0, src, ln))
                p += 13
            else:
                ln, = struct.unpack_from("<I", body, p + 1)
                ops.append((1, body[p + 5:p + 5 + ln]))
                p += 5 + ln
        records.append((at, length, ops))
    return src_size, dst_size, src_md5, dst_sha, note, records


# Black Label RANK bar art (research/phase19): 80 x 14 pixels in the ibarablk_u2 NAND dump, big-endian 16-bit,
# screen pixel (x, y) at BL_ART_BASE + x * 512 - y * 2. Written row-major (big-endian words) after BL_ART_TAG.
BL_U2_SIZE = 138_412_032
BL_U2_CRC = 0x5E46BE44
BL_ART_BASE = 0x06D269F0
BL_ART_W, BL_ART_H = 80, 14
BL_ART_TAG = b"BLRANKBAR-ART-01"


def read_bl_art(path, data=None):
    """The bar's 2,240 art bytes from the user's ibarablk ROM (zip or the u2 file), checked by size and CRC."""
    if data is None:
        data = read_bl_rom(path)
    out = bytearray()
    for y in range(BL_ART_H):
        for x in range(BL_ART_W):
            out += data[BL_ART_BASE + x * 512 - y * 2:BL_ART_BASE + x * 512 - y * 2 + 2]
    return bytes(out)


def inject_bl_art(iso, at, art):
    """Write the art after the tag found at ISO offset `at`."""
    with open(iso, "r+b") as f:
        f.seek(at + len(BL_ART_TAG))
        f.write(art)


# Black Label select screen (research/phase20): six 256 x 128 PSMCT16 texture pages after SELECT_TAG in the
# executable's art segment, assembled from the ROM's blitter images as described by bl_select_atlas.json.
SELECT_TAG = b"BLSELECT-ART-01\0"
SELECT_ON = b"BLSELECT-ART-ON\0"
SELECT_PAGES = 6


def build_select_pages(rom_data, atlas):
    rects = atlas["rects"]
    pages = bytearray(SELECT_PAGES * 0x10000)

    def pixel(x, y):
        for dx, dy, w, h, off in reversed(rects):
            if dx <= x < dx + w and dy <= y < dy + h:
                return struct.unpack_from(">H", rom_data, off + ((y - dy) * w + (x - dx)) * 2)[0]
        return 0
    for sx, sy, w, h, page, px, py in atlas["sprites"]:
        for i in range(w):          # screen row i = blitter column sx + w - 1 - i
            for j in range(h):      # screen column j = blitter row sy + j
                v = pixel(sx + w - 1 - i, sy + j)
                c = (v & 0x8000) | (v & 31) << 10 | (v & 0x3E0) | ((v >> 10) & 31)
                struct.pack_into("<H", pages, page * 0x10000 + ((py + i) * 256 + px + j) * 2, c)
    return bytes(pages)


def read_bl_rom(path):
    """The whole ibarablk_u2 (zip or file), checked by size and CRC."""
    path = Path(path)
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            names = [i for i in z.infolist() if i.file_size == BL_U2_SIZE]
            if not names or names[0].CRC != BL_U2_CRC:
                raise SystemExit(f"{path}: no Black Label ibarablk_u2 ({BL_U2_SIZE:,} bytes, CRC {BL_U2_CRC:08x})")
            with z.open(names[0]) as f:
                return f.read()
    data = path.read_bytes()
    if len(data) != BL_U2_SIZE or zlib.crc32(data) != BL_U2_CRC:
        raise SystemExit(f"{path} is not the Black Label ibarablk_u2 ({BL_U2_SIZE:,} bytes, CRC {BL_U2_CRC:08x})")
    return data


def inject_bl_select(iso, at, pages):
    with open(iso, "r+b") as f:
        f.seek(at)
        f.write(SELECT_ON)
        f.write(pages)


def digest(path, algo, label):
    h = hashlib.new(algo)
    size = path.stat().st_size
    done = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
            done += len(chunk)
            if done % (1 << 28) < (1 << 22):
                print(f"\r    {label} {done * 100 // size:3d}%", end="", flush=True)
    print(f"\r    {label} 100%")
    return h.hexdigest()


def main(argv):
    rom = None
    if "--bl-rom" in argv:
        i = argv.index("--bl-rom")
        if i + 1 >= len(argv):
            print(__doc__)
            return 2
        rom = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if len(argv) not in (2, 3):
        print(__doc__)
        return 2
    source = Path(argv[0])
    output = Path(argv[1])
    patch = Path(argv[2]) if len(argv) == 3 else HERE / "ibara_kuro.patch"
    rom_data = read_bl_rom(rom) if rom else None
    art = read_bl_art(rom, rom_data) if rom else None
    if output.exists():
        raise SystemExit(f"{output} already exists; choose a new name")
    src_size, dst_size, src_md5, dst_sha, note, records = read_patch(patch)
    if dst_size > src_size:  # project rule: the disc image never grows
        raise SystemExit(f"patch would grow the disc ({dst_size:,} > {src_size:,} bytes); refusing")
    print(f"Ibara KURO patch: {note}")
    print("1/3 checking your ISO ...")
    if source.stat().st_size != src_size or digest(source, "md5", "MD5") != src_md5:
        raise SystemExit("This is not the retail Japanese 'Ibara (Japan).iso' (SLPM-66301, MD5 " + src_md5 + ").")
    print("2/3 writing the new ISO ...")
    shutil.copyfile(source, output)
    art_at = sel_at = None
    with source.open("rb") as src, output.open("r+b") as out:
        out.truncate(dst_size)
        for at, length, ops in records:
            buf = bytearray()
            for op in ops:
                if op[0] == 0:
                    src.seek(op[1])
                    buf += src.read(op[2])
                else:
                    buf += op[1]
            if len(buf) != length:
                raise SystemExit("patch is damaged (record length mismatch)")
            out.seek(at)
            out.write(buf)
            k = buf.find(BL_ART_TAG)
            if k >= 0:
                art_at = at + k
            k = buf.find(SELECT_TAG)
            if k >= 0:
                sel_at = at + k
    print("3/3 verifying ...")
    if digest(output, "sha256", "SHA-256") != dst_sha:
        output.unlink()
        raise SystemExit("Verification failed; the output was deleted. Re-download the patch and try again.")
    if art and art_at is not None:
        inject_bl_art(output, art_at, art)
        print("Black Label RANK bar artwork copied from your ROM.")
    if rom_data and sel_at is not None:
        atlas = json.loads((HERE / "bl_select_atlas.json").read_text())
        inject_bl_select(output, sel_at, build_select_pages(rom_data, atlas))
        print("Black Label select screen artwork copied from your ROM.")
    elif art:
        print("Note: this patch has no place for the RANK bar artwork; it was not added.")
    print(f"Done: {output}")
    print("Boot it, press Start at the title; KURO is the third row of Mode Select (Circle to enter).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
