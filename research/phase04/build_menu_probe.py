#!/usr/bin/env python3
"""Build a separate Ibara test ISO that launches a standalone EE payload."""

import argparse
import hashlib
from pathlib import Path
import re
import struct
import sys

import ibara_complete_audit as retail
import ibara_complete_button_prototype as atlas

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'phase03'))
import ibara_complete_bootstrap as disc

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import build_pnach as video


# Zero padding begins after the final instruction at 0x001D4280.
INIT = 0x001D4284
DISPATCH = 0x001D42A0
LABEL = 0x001D42C8
PATH = 0x001D42D8
EMPTY_DESCRIPTION = 0x001D42F0
PAYLOAD_ARGV = 0x001D42F4  # argv[1] for the payload: pointer to PAYLOAD_ARG
PAYLOAD_ARG = 0x001D42F8   # "S=0" (screen mode), refreshed by ps2/hooks/video.c when present
RETAIL_BASE = 0x00100000
RETAIL_LOAD_OFFSET = 0x80
LABEL_BOX = (112, 192, 224, 208)
DEFAULT_LABEL = 'ELF PROBE'
# Additional field-state writes from cave-ps2-240p v0.1.0-beta.1.
FIELD_STATE_EDITS = [
    (0x001B29D4, 0xAF829574, 0xAF809574),
    (0x001B2A60, 0xAF839550, 0xAF809550),
    (0x001B2A80, 0xAF829574, 0xAF809574),
]
VIDEO_PROFILES = {
    'retail': (),
    '240p_core': video.VIDEO_EDITS,
    '240p_halfpixel': video.VIDEO_EDITS + video.HALFPIXEL_EDITS,
    '240p_cave_beta': video.VIDEO_EDITS + video.HALFPIXEL_EDITS + FIELD_STATE_EDITS,
    # Yoko interlaced without texture filtering, Tate 240p: static part only (no bilinear 0x001AF11C, the two Tate
    # display tables 0x001DD200 / 0x001DD240). The interlace flag, half-pixel and field-state words are switched at
    # runtime by ps2/hooks/video.c, which the builders add with this profile (VIDEO_HOOK_PROFILES).
    'auto': [e for e in video.VIDEO_EDITS if e[0] == 0x001AF11C or 0x001DD200 <= e[0] < 0x001DD280],
}
VIDEO_HOOK_PROFILES = {'auto'}
LOAD_EXEC_PS2 = 0x24030006  # addiu v1, zero, 6
SYSCALL = 0x0000000C


def jump(address):
    return 0x08000000 | (address >> 2)


def branch_not_equal(rs, rt, start, target):
    delta = (target - start - 4) // 4
    if not -32768 <= delta <= 32767:
        raise ValueError(f'Branch target out of range at {start:08X}')
    return 0x14000000 | (rs << 21) | (rt << 16) | (delta & 0xFFFF)


LABELS = 0x002A9090        # six label-record pointers, one per row (row 5 is the added entry)
DESCRIPTIONS = 0x002A90B0  # six two-word description entries, one per row
ROW_LABELS = (0x002A8E80, 0x002A8E90, 0x002A8EA0, 0x002A8EB0, 0x002A8EC0)  # Arcade Arrange Gallery Option Exit
ROW_DESCRIPTIONS = ((0x002A8EF0, 0x002A8F00), (0x002A8F10, 0x002A8F20), (0x002A8F30, 0x002A8F40),
                    (0x002A8F50, 0x002A8F60), (0x002A8F70, 0))


def menu_elf(original, video_profile='retail', position=5):
    """position: row of the added entry, 5 = bottom (after Exit) or 2 = third (after Arcade and Arrange).

    Rows are drawn at fixed heights by index, so moving the entry permutes the label and description tables and the
    accept dispatcher (0x001CA798): with position 2, index 2 launches the payload and Gallery, Option and Exit move
    to indices 3, 4 and 5."""
    if position not in (2, 5):
        raise ValueError('position must be 2 (third row) or 5 (bottom)')
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
    }
    order = list(range(5))
    order.insert(position, None)  # row -> original item (None = added entry)
    for row, item in enumerate(order):
        label = LABEL if item is None else ROW_LABELS[item]
        desc = (EMPTY_DESCRIPTION, EMPTY_DESCRIPTION) if item is None else ROW_DESCRIPTIONS[item]
        before_label = ROW_LABELS[row] if row < 5 else 0
        before_desc = ROW_DESCRIPTIONS[row] if row < 5 else (0, 0)
        if label != before_label:
            edits[LABELS + 4 * row] = (before_label, label)
        for k in range(2):
            if desc[k] != before_desc[k]:
                edits[DESCRIPTIONS + 8 * row + 4 * k] = (before_desc[k], desc[k])
    if position == 2:  # accept dispatcher: Gallery 2->3, Option 3->4, Exit 4->5
        # Exit has a null second help line. The draw path must skip it at the new row.
        edits[0x001CA648] = (0x24020004, 0x24020005)
        edits[0x001CA7B8] = (0x24020002, 0x24020003)
        edits[0x001CA7C8] = (0x24020003, 0x24020004)
        edits[0x001CA7D8] = (0x24020004, 0x24020005)
        # Returning from OPTION restores Mode Select row 3 (its old index): make it 4. Cancel path stores a plain 3
        # (0x001CD1E8); the EXIT-item path compares the Option cursor with 3 and stores the same register, so the
        # empty delay slot after that compare adds 1 (the branch target reloads v0 before using it, 0x001CD220).
        edits[0x001CD1E8] = (0x24020003, 0x24020004)
        edits[0x001CD35C] = (0x00000000, 0x24420001)
    sections = {
        INIT: (
            0x3C080050, 0x24090038,  # t0 = animation array base, t1 = row anchor
            0xAD090634, 0xAD090654, 0xAD000674,  # Seed actual, target, and fade.
            jump(0x001CA360), 0xAF8090E0,  # Replay the displaced store in the delay slot.
        ),
        DISPATCH: (
            0x24020000 | position,  # v0 = row of the added entry
            branch_not_equal(3, 2, DISPATCH + 4, DISPATCH + 32),
            0x3C04001D, 0x248442D8,  # a0 = disc path
            0x24050001, 0x2486001C,  # argc = 1, argv = PAYLOAD_ARGV (a0 + 0x1C)
            LOAD_EXEC_PS2, SYSCALL,
            jump(0x001CA5AC), 0,  # Resume normal drawing if the syscall returns.
        ),
        LABEL: (0x30700002, 0x0F6F0000, 0, 0),  # Texture 2, bottom-origin UV, 112×16.
        PATH: struct.unpack('<6I', (b'cdrom0:\\' + disc.PROBE_FILENAME).ljust(24, b'\0')),
        EMPTY_DESCRIPTION: (0,),
        PAYLOAD_ARGV: (PAYLOAD_ARG,),
        PAYLOAD_ARG: (0x00303D53,),  # "S=0\0"
    }
    for address, words in sections.items():
        for index, word in enumerate(words):
            destination = address + 4 * index
            if destination in edits:
                raise ValueError(f'Overlapping writes at {destination:08X}')
            edits[destination] = (0, word)
    for address, before, after in VIDEO_PROFILES[video_profile]:
        if address in edits:
            raise ValueError(f'Video and launcher writes overlap at {address:08X}')
        edits[address] = (before, after)
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
    elf_header_size, segment_header_size, count = struct.unpack_from('<HHH', probe, 40)
    if ((kind, machine, version) != (2, 8, 1) or elf_header_size != 52 or
            segment_header_size != 32 or count == 0 or table < elf_header_size or
            table + count * segment_header_size > len(probe) or entry & 3):
        raise ValueError('Invalid MIPS executable header or program headers')
    executable_entry = False
    for index in range(count):
        segment, offset, address, _, size, memory, flags, _ = struct.unpack_from(
            '<8I', probe, table + index * segment_header_size,
        )
        if segment != 1:
            continue
        if size > memory or offset + size > len(probe) or address + memory > 0x02000000:
            raise ValueError('A probe load segment exceeds the file or EE RAM')
        executable_entry |= bool(flags & 1 and address <= entry < address + size)
    if not executable_entry:
        raise ValueError('The probe entry point must be inside a file-backed executable segment')
    return probe


def companion_layout(specifications, records, probe_size, include_probe=True):
    occupied_names = {record['name'].split(b';', 1)[0] for record in records}
    occupied_names.add(disc.PROBE_FILENAME.split(b';', 1)[0])
    end_lba = disc.NEW_FILE_LBA + (probe_size + disc.SECTOR - 1) // disc.SECTOR if include_probe else disc.NEW_FILE_LBA
    payload_records = [disc.make_file_record(disc.PROBE_FILENAME, disc.NEW_FILE_LBA, probe_size)] if include_probe else []
    companions = []
    for specification in specifications:
        name, separator, path = specification.partition('=')
        if (not separator or not path or
                not re.fullmatch(r'[A-Za-z0-9_]{1,8}(?:\.[A-Za-z0-9_]{1,3})?', name)):
            raise ValueError(f'Use --disc-file NAME.EXT=PATH with an ISO 8.3 filename: {specification!r}')
        filename = name.upper().encode('ascii')
        if filename in occupied_names:
            raise ValueError(f'Disc filename is already in use: {name.upper()}')
        occupied_names.add(filename)
        source = Path(path)
        if not source.is_file():
            raise ValueError(f'Companion must be a regular file: {source}')
        size = source.stat().st_size
        sectors = max(1, (size + disc.SECTOR - 1) // disc.SECTOR)
        if end_lba + sectors > disc.NEXT_ORIGINAL_FILE_LBA:
            raise ValueError(f'Companion files exceed the reserved disc extent at {name.upper()}')
        payload_records.append(disc.make_file_record(filename + b';1', end_lba, size))
        companions.append((source, end_lba * disc.SECTOR, size))
        end_lba += sectors
    directory_entries = b''.join(payload_records)
    if disc.ORIGINAL_ROOT_LEN + len(directory_entries) > disc.SECTOR:
        raise ValueError('Added files exceed the available root directory space')
    return directory_entries, companions, end_lba


def write_companion(target, path, offset, size, chunk_size):
    with path.open('rb') as source:
        target.seek(offset)
        remaining = size
        while remaining:
            length = min(remaining, chunk_size)
            block = source.read(length)
            if len(block) != length:
                raise ValueError(f'Companion changed size during build: {path}')
            target.write(block)
            remaining -= length
        if source.read(1):
            raise ValueError(f'Companion changed size during build: {path}')
        source.seek(0)
        target.seek(offset)
        remaining = size
        while remaining:
            length = min(remaining, chunk_size)
            if target.read(length) != source.read(length):
                raise ValueError(f'Output verification failed for companion: {path}')
            remaining -= length


def label_writes(source, files, text=DEFAULT_LABEL):
    from PIL import Image, ImageDraw, ImageFont

    if not text.strip() or not text.isprintable():
        raise ValueError('The launcher label must be a single printable line')
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
        _, top, _, bottom = draw.textbbox((0, 0), text, font=font, anchor='lm', stroke_width=1)
        vertical = (label.height - (bottom - top)) // 2 - top
    left, top, right, bottom = draw.textbbox((4, vertical), text, font=font, anchor='lm', stroke_width=1)
    if left < 0 or top < 0 or right > label.width or bottom > label.height:
        raise ValueError('The launcher label must fit in the 112×16-pixel slot; choose a shorter label')
    draw.text(
        (4, vertical), text, font=font, anchor='lm', fill=(255, 244, 162, 255),
        stroke_width=1, stroke_fill=(13, 22, 44, 255),
    )
    left, top, _, bottom = LABEL_BOX
    return [(pixels + y * width + left, row.tobytes()) for y, row in zip(range(top, bottom), atlas.quantize(label, palette))]


def build(source, output, probe_path=None, *, label=DEFAULT_LABEL, video_profile='retail', disc_files=(), position=5,
          executable_hook=None, payload=True):
    """payload=False: no separate executable on the disc (instant KURO: executable_hook makes the added row act
    inside the frontend executable instead of loading one)."""
    if source.resolve() == output.resolve():
        raise ValueError('Choose a separate output path')
    probe = b'' if not payload else returning_probe() if probe_path is None else read_probe_elf(probe_path)
    pvd, root, records, _, source_sha = disc.check_source(source)
    rows, companions, end_lba = companion_layout(disc_files, records, len(probe), include_probe=payload)
    original, files, boot = retail.load_input(source)
    end = disc.ORIGINAL_ROOT_LEN + len(rows)
    pvd, root = bytearray(pvd), bytearray(root)
    pvd[166:174] = disc.pair32(end)
    root[disc.ORIGINAL_ROOT_LEN:end] = rows
    for record in records[:2]:
        offset = record['offset'] + 10
        root[offset:offset + 8] = disc.pair32(end)

    executable = menu_elf(original, video_profile, position)
    boot_lba = boot['lba']
    if executable_hook is not None:  # e.g. bake the runtime video hook into the frontend executable
        executable = executable_hook(bytes(executable))
        capacity = (boot['bytes'] + disc.SECTOR - 1) // disc.SECTOR * disc.SECTOR
        if len(executable) != boot['bytes']:
            own = [r for r in records if r['name'] == boot['name'].encode() or r['name'] == boot['name']]
            if len(own) != 1:
                raise ValueError('Boot executable record not found in the root directory')
            if len(executable) > capacity:
                # Too big for its extent (the next retail file follows it): place the executable in the free
                # extent after the payload and companions, like KURO.ELF; the retail copy stays where it was.
                boot_lba = end_lba
                end_lba += (len(executable) + disc.SECTOR - 1) // disc.SECTOR
                if end_lba > disc.NEXT_ORIGINAL_FILE_LBA:
                    raise ValueError('No free disc extent left for the frontend executable')
                root[own[0]['offset'] + 2:own[0]['offset'] + 10] = disc.pair32(boot_lba)
            root[own[0]['offset'] + 10:own[0]['offset'] + 18] = disc.pair32(len(executable))
    writes = [
        (16 * disc.SECTOR, pvd),
        (disc.ORIGINAL_ROOT_LBA * disc.SECTOR, root),
        *([(disc.NEW_FILE_LBA * disc.SECTOR, probe)] if payload else []),
        (boot_lba * disc.SECTOR, executable),
        *label_writes(source, files, label),
    ]
    with source.open('rb') as original_iso, output.open('x+b') as target:
        try:
            zeros = bytes(4 * 1024 * 1024)
            original_iso.seek(disc.NEW_FILE_LBA * disc.SECTOR)
            remaining = (end_lba - disc.NEW_FILE_LBA) * disc.SECTOR
            while remaining:
                size = min(remaining, len(zeros))
                if original_iso.read(size) != zeros[:size]:
                    raise ValueError('The payload or a companion would overwrite occupied disc sectors')
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
            for path, offset, size in companions:
                write_companion(target, path, offset, size, len(zeros))
            for offset, contents in writes:
                if disc.read_at(target, offset, len(contents)) != contents:
                    raise ValueError(f'Output verification failed at disc offset {offset:08X}')
            if disc.digest_file(source) != source_sha:
                raise ValueError('Original ISO changed during build')
        except BaseException:
            try:
                target.close()
            finally:
                output.unlink(missing_ok=True)
            raise
    return video.xor_elf_crc(executable), hashlib.sha256(executable).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='Exact original Japanese Ibara ISO')
    parser.add_argument('--output', type=Path, required=True, help='New test ISO path')
    parser.add_argument('--payload-elf', '--probe-elf', type=Path,
                        help='Use a custom EE executable in place of the timed probe')
    parser.add_argument('--disc-file', action='append', default=[], metavar='NAME=PATH',
                        help='Add a companion file to the disc root (repeatable, ISO 8.3 name)')
    parser.add_argument('--label', default=DEFAULT_LABEL, help='Short label for the sixth menu entry')
    parser.add_argument('--position', type=int, choices=(2, 5), default=5,
                        help='Row of the added entry: 5 = bottom (default), 2 = third, after Arcade and Arrange')
    parser.add_argument('--video-profile', choices=VIDEO_PROFILES, default='retail',
                        help='Video profile for the retail frontend')
    args = parser.parse_args()
    try:
        crc, sha256 = build(args.source, args.output, args.payload_elf, label=args.label,
                            video_profile=args.video_profile, disc_files=args.disc_file,
                            position=args.position)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f'Created {args.output}')
    print(f'Retail ELF CRC: {crc:08X} ({args.video_profile})')
    print(f'Retail ELF SHA-256: {sha256}')


if __name__ == '__main__':
    main()
