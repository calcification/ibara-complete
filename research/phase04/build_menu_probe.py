#!/usr/bin/env python3
"""Build a separate Ibara test ISO with an original ELF handoff probe."""

import argparse
from pathlib import Path
import struct
import sys

import ibara_complete_audit as retail
import ibara_complete_button_prototype as atlas

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'phase03'))
import ibara_complete_bootstrap as disc


# Zero padding begins after the final instruction at 0x001D4280.
INIT = 0x001D4284
DISPATCH = 0x001D42A0
LABEL = 0x001D42C8
PATH = 0x001D42D8
EMPTY_DESCRIPTION = 0x001D42F0
RETAIL_BASE = 0x00100000
RETAIL_LOAD_OFFSET = 0x80
LABEL_BOX = (112, 192, 224, 208)
LOAD_EXEC_PS2 = 0x24030006  # addiu v1, zero, 6
SYSCALL = 0x0000000C


def jump(address):
    return 0x08000000 | (address >> 2)


def branch_not_equal(rs, rt, start, target):
    delta = (target - start - 4) // 4
    if not -32768 <= delta <= 32767:
        raise ValueError(f'Branch target out of range at {start:08X}')
    return 0x14000000 | (rs << 21) | (rt << 16) | (delta & 0xFFFF)


def menu_elf(original):
    elf = bytearray(original)
    edits = {
        0x001CA358: (0xAF8090E0, jump(INIT)),  # Initialize the sixth row each time.
        0x001CA44C: (0x28410005, 0x28410006),  # Downward bounds.
        0x001CA494: (0x29020005, 0x29020006),  # Animation target bounds.
        0x001CA56C: (0x28880005, 0x28880006),  # Highlight bounds.
        0x001CA6DC: (0x2A020005, 0x2A020006),  # Draw bounds.
        0x001CA720: (0x24020004, 0x24020005),  # Up wraps to index 5.
        # Indices 0–3 have already branched. Index 4 still falls through to Exit.
        0x001CA7DC: (0x1462FF73, branch_not_equal(3, 2, 0x001CA7DC, DISPATCH)),
        0x002A90A4: (0, LABEL),
        0x002A90D8: (0, EMPTY_DESCRIPTION),
        0x002A90DC: (0, EMPTY_DESCRIPTION),
    }
    sections = {
        INIT: (
            0x3C080050, 0x24090038,  # t0 = animation array base, t1 = row anchor
            0xAD090634, 0xAD090654, 0xAD000674,  # Seed actual, target, and fade.
            jump(0x001CA360), 0xAF8090E0,  # Replay the displaced store in the delay slot.
        ),
        DISPATCH: (
            0x24020005,  # v0 = 5
            branch_not_equal(3, 2, DISPATCH + 4, DISPATCH + 32),
            0x3C04001D, 0x248442D8,  # a0 = disc path
            0x00002821, 0x00003021,  # argc = 0, argv = NULL
            LOAD_EXEC_PS2, SYSCALL,
            jump(0x001CA5AC), 0,  # Resume normal drawing if the syscall returns.
        ),
        LABEL: (0x30700002, 0x0F6F0000, 0, 0),  # Texture 2, bottom-origin UV, 112×16.
        PATH: struct.unpack('<6I', (b'cdrom0:\\' + disc.PROBE_FILENAME).ljust(24, b'\0')),
        EMPTY_DESCRIPTION: (0,),
    }
    for address, words in sections.items():
        for index, word in enumerate(words):
            destination = address + 4 * index
            if destination in edits:
                raise ValueError(f'Overlapping writes at {destination:08X}')
            edits[destination] = (0, word)
    for address, (before, after) in edits.items():
        offset = address - RETAIL_BASE + RETAIL_LOAD_OFFSET
        if struct.unpack_from('<I', elf, offset)[0] != before:
            raise ValueError(f'Unexpected original word at EE address {address:08X}')
        struct.pack_into('<I', elf, offset, after)
    return elf


def returning_probe():
    # Same original GS writes as the Phase 3 probe, followed by a bounded wait
    # using CP0 Count. The successful return path cold-loads the retail ELF.
    words = (
        0x3C081200, 0x24090020, 0xFD090000, 0x3C0900FF, 0x352900FF, 0xFD0900E0,
        0x400A4800, 0x3C0B0600,  # Initial cycle count and wait duration.
        0x400C4800, 0x018A6023, 0x018B602B, 0x1580FFFC, 0,
        0x3C040010, 0x24840054, 0x00002821, 0x00003021,
        LOAD_EXEC_PS2, SYSCALL, 0x1000FFFF, 0,
    )
    code = struct.pack(f'<{len(words)}I', *words) + b'cdrom0:\\SLPM_663.01;1\0'
    header = bytearray(disc.build_probe_elf()[:RETAIL_LOAD_OFFSET])
    struct.pack_into('<II', header, 68, len(code), len(code))  # PT_LOAD file and memory sizes.
    return bytes(header) + code


def read_probe_elf(path):
    available = (disc.NEXT_ORIGINAL_FILE_LBA - disc.NEW_FILE_LBA) * disc.SECTOR
    if not 52 <= path.stat().st_size <= available:
        raise ValueError('The probe ELF does not fit in the reserved disc extent')
    probe = path.read_bytes()
    if len(probe) < 52 or probe[:7] != b'\x7fELF\x01\x01\x01':
        raise ValueError('The probe must be a little-endian ELF32 executable')
    kind, machine, version, entry, table = struct.unpack_from('<HHIII', probe, 16)
    header_size, count = struct.unpack_from('<HH', probe, 42)
    if ((kind, machine, version) != (2, 8, 1) or header_size != 32 or count == 0 or
            table < 52 or table + count * header_size > len(probe) or entry & 3):
        raise ValueError('Invalid MIPS executable header or program headers')
    executable_entry = False
    for index in range(count):
        segment, offset, address, _, size, memory, flags, _ = struct.unpack_from(
            '<8I', probe, table + index * header_size,
        )
        if segment != 1:
            continue
        if size > memory or offset + size > len(probe) or address + memory > 0x02000000:
            raise ValueError('A probe load segment exceeds the file or EE RAM')
        executable_entry |= bool(flags & 1 and address <= entry < address + size)
    if not executable_entry:
        raise ValueError('The probe entry point must be inside a file-backed executable segment')
    return probe


def label_writes(source, files):
    from PIL import Image, ImageDraw, ImageFont

    pdm = next(record for record in files if record['name'].split(';')[0].upper() == 'IBARAR.PDM')
    with source.open('rb') as iso:
        offset = pdm['lba'] * disc.SECTOR + 0x2D20800  # Resource 945.
        header = disc.read_at(iso, offset, 16)
        if header[:4] != b'TIM2':
            raise ValueError('Unexpected magic for menu label atlas')
        picture = offset + (128 if header[5] else 16)
        fields = struct.unpack('<IIIHHBBBBHH', disc.read_at(iso, picture, 24))
        _, palette_size, pixel_size, header_size, _, _, _, palette_type, image_type, width, height = fields
        if (palette_size, pixel_size, palette_type & 0x1F, image_type, width, height) != (1024, 65536, 3, 5, 256, 256):
            raise ValueError('Unexpected menu label atlas layout')
        pixels = picture + header_size
        original = disc.read_at(iso, pixels, pixel_size)
        palette = atlas.palette_from_bytes(disc.read_at(iso, pixels + pixel_size, palette_size), palette_type)
    tile = atlas.original_image(original, palette).crop(LABEL_BOX)
    if tile.getchannel('A').getextrema() != (0, 0):
        raise ValueError('The probe label would overlap existing atlas artwork')
    label = Image.new('RGBA', tile.size)
    draw = ImageDraw.Draw(label)
    vertical = 7
    try:
        font = ImageFont.truetype('DejaVuSans-Bold.ttf', 13)
    except OSError:
        font = ImageFont.load_default()
        _, top, _, bottom = draw.textbbox((0, 0), 'ELF PROBE', font=font, anchor='lm', stroke_width=1)
        vertical = (label.height - (bottom - top)) // 2 - top
    draw.text(
        (4, vertical), 'ELF PROBE', font=font, anchor='lm', fill=(255, 244, 162, 255),
        stroke_width=1, stroke_fill=(13, 22, 44, 255),
    )
    left, top, _, bottom = LABEL_BOX
    return [(pixels + y * width + left, row.tobytes()) for y, row in zip(range(top, bottom), atlas.quantize(label, palette))]


def build(source, output, probe_path=None):
    if source.resolve() == output.resolve():
        raise ValueError('Choose a separate output path')
    probe = returning_probe() if probe_path is None else read_probe_elf(probe_path)
    pvd, root, records, _, source_sha = disc.check_source(source)
    original, files, boot = retail.load_input(source)
    row = disc.make_file_record(disc.PROBE_FILENAME, disc.NEW_FILE_LBA, len(probe))
    end = disc.ORIGINAL_ROOT_LEN + len(row)
    pvd, root = bytearray(pvd), bytearray(root)
    pvd[166:174] = disc.pair32(end)
    root[disc.ORIGINAL_ROOT_LEN:end] = row
    for record in records[:2]:
        offset = record['offset'] + 10
        root[offset:offset + 8] = disc.pair32(end)

    writes = [
        (16 * disc.SECTOR, pvd),
        (disc.ORIGINAL_ROOT_LBA * disc.SECTOR, root),
        (disc.NEW_FILE_LBA * disc.SECTOR, probe),
        (boot['lba'] * disc.SECTOR, menu_elf(original)),
        *label_writes(source, files),
    ]
    with source.open('rb') as original_iso, output.open('x+b') as target:
        try:
            zeros = bytes(4 * 1024 * 1024)
            original_iso.seek(disc.NEW_FILE_LBA * disc.SECTOR)
            remaining = (len(probe) + disc.SECTOR - 1) // disc.SECTOR * disc.SECTOR
            while remaining:
                size = min(remaining, len(zeros))
                if original_iso.read(size) != zeros[:size]:
                    raise ValueError('The probe would overwrite occupied disc sectors')
                remaining -= size
            original_iso.seek(0)
            while block := original_iso.read(len(zeros)):
                if block == zeros[:len(block)]:
                    target.seek(len(block), 1)
                else:
                    target.write(block)
            target.truncate(original_iso.tell())
            for offset, contents in writes:
                target.seek(offset)
                target.write(contents)
            for offset, contents in writes:
                if disc.read_at(target, offset, len(contents)) != contents:
                    raise ValueError(f'Output verification failed at disc offset {offset:08X}')
            if disc.digest_file(source) != source_sha:
                raise ValueError('Original ISO changed during build')
        except Exception:
            target.close()
            output.unlink(missing_ok=True)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='Exact original Japanese Ibara ISO')
    parser.add_argument('--output', type=Path, required=True, help='New test ISO path')
    parser.add_argument('--probe-elf', type=Path, help='Use a custom EE executable in place of the timed probe')
    args = parser.parse_args()
    try:
        build(args.source, args.output, args.probe_elf)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f'Created {args.output}')


if __name__ == '__main__':
    main()
