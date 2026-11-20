#!/usr/bin/env python3
"""Ibara Complete research utility: read-only PS2 ELF / ISO structural audit.

Usage:
    python ibara_complete_audit.py SLPM_663.01
    python ibara_complete_audit.py "Ibara (Japan).iso" --json audit.json

Standard-library only. No game data is bundled, copied to output, or modified.
This is a structural auditor, not a Black Label patcher.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

SECTOR = 2048
EXPECTED_NAME = 'SLPM_663.01'
EXPECTED_ISO_ELF_LBA_FROM_PRIOR_PATCH = 1919173
ELF_OFFSET = 0x80
ELF_LOAD = 0x100000
MENUS = {
    'arcade_main': (0x1A90A0, 4),
    'arrange_main': (0x1A90C8, 3),
    'arrange_options': (0x1A90E0, 4),
    'arcade_difficulty': (0x1A9180, 4),
}
# These are independently inspected code addresses, NOT function entries.
CODE_POINTS = {
    'arcade_menu_table_ref': 0x1CA974,
    'arrange_menu_table_ref': 0x1CCAE4,
    'arcade_mode_table_ref': 0x1CABD0,
    'arrange_options_table_ref': 0x1CCDDC,
    'arcade_accept_dispatch': 0x1CAA88,
    'arrange_accept_dispatch': 0x1CCBF4,
}
# Original words from a previously verified 240p patch list, evaluated against
# the ELF read from user-provided data. RAM addresses, not ISO offsets.
PATCH_PROBES = {
    0x001AD250: 0x24050001,
    0x001AF11C: 0x24040060,
    0x001DD1C0: 0x00000000,
    0x001DD1D0: 0x000000F0,
    0x001B29D4: 0xAF829574,
    0x001B2A60: 0xAF839550,
    0x001B2A80: 0xAF829574,
}

def u32(buf, pos):
    return struct.unpack_from('<I', buf, pos)[0]

def parse_dir_record(buf, pos):
    if pos >= len(buf) or not buf[pos]:
        return None
    length = buf[pos]
    if pos + length > len(buf) or length < 34:
        return None
    extent = u32(buf, pos + 2)
    byte_len = u32(buf, pos + 10)
    flags = buf[pos + 25]
    n = buf[pos + 32]
    name = buf[pos + 33:pos + 33 + n].decode('ascii', errors='replace')
    if n == 1 and name in ('\x00', '\x01'):
        return None
    return {'name': name, 'lba': extent, 'bytes': byte_len,
            'directory': bool(flags & 2), 'record_length': length}

def scan_iso(fh):
    fh.seek(SECTOR * 16)
    pvd = fh.read(SECTOR)
    if len(pvd) != SECTOR or pvd[1:6] != b'CD001' or pvd[0] != 1:
        raise ValueError('Not a plain 2048-byte/sector ISO9660 image (missing primary volume descriptor)')
    root = parse_dir_record(pvd, 156)
    if not root or not root['directory']:
        # Special root name \x00 is deliberately rejected above; parse its extent directly.
        root = {'name': '', 'lba': u32(pvd, 158), 'bytes': u32(pvd, 166), 'directory': True}
    result = []
    todo = [('', root)]
    seen = set()
    while todo:
        parent, entry = todo.pop()
        tag = (entry['lba'], entry['bytes'])
        if tag in seen:
            continue
        seen.add(tag)
        if len(seen) > 10000:
            raise ValueError('Unreasonable directory count; possible filesystem loop')
        fh.seek(entry['lba'] * SECTOR)
        d = fh.read(entry['bytes'])
        j = 0
        while j < len(d):
            if d[j] == 0:
                j = ((j // SECTOR) + 1) * SECTOR
                continue
            rec = parse_dir_record(d, j)
            reclen = d[j]
            j += reclen
            if rec is None:
                continue
            full = parent + '/' + rec['name']
            rec['path'] = full
            result.append(rec)
            if rec['directory']:
                todo.append((full, rec))
    result.sort(key=lambda x: x['path'])
    return result

def load_input(p):
    with p.open('rb') as fh:
        first = fh.read(4)
        if first == b'\x7fELF':
            return p.read_bytes(), [], None
        items = scan_iso(fh)
        matches = [f for f in items if f['name'].split(';')[0].upper() == EXPECTED_NAME]
        if len(matches) != 1:
            raise ValueError(f'Expected one {EXPECTED_NAME} in ISO9660 listing, found {len(matches)}')
        entry = matches[0]
        fh.seek(entry['lba'] * SECTOR)
        elf = fh.read(entry['bytes'])
        if elf[:4] != b'\x7fELF':
            raise ValueError('Disc boot file is not an ELF')
        return elf, items, entry

def elf_summary(elf):
    if elf[:4] != b'\x7fELF' or elf[4] != 1 or elf[5] != 1:
        raise ValueError('Expected ELF32 little-endian executable')
    e_machine = struct.unpack_from('<H', elf, 18)[0]
    entry = u32(elf, 24)
    phoff = u32(elf, 28)
    phentsize = struct.unpack_from('<H', elf, 42)[0]
    phnum = struct.unpack_from('<H', elf, 44)[0]
    loads = []
    for i in range(phnum):
        o = phoff + i * phentsize
        fields = struct.unpack_from('<8I', elf, o)
        if fields[0] == 1:
            loads.append({'offset': fields[1], 'vaddr': fields[2],
                          'file_bytes': fields[4], 'memory_bytes': fields[5],
                          'flags': fields[6]})
    if not loads:
        raise ValueError('ELF lacks PT_LOAD')
    return {'file_bytes': len(elf), 'sha256': hashlib.sha256(elf).hexdigest(),
            'machine': e_machine, 'entry': entry, 'loads': loads}

def read_ram(elf, loads, vaddr, size):
    for seg in loads:
        if seg['vaddr'] <= vaddr and vaddr + size <= seg['vaddr'] + seg['file_bytes']:
            at = seg['offset'] + vaddr - seg['vaddr']
            return elf[at:at + size]
    raise ValueError('Address 0x%X not backed by a file segment' % vaddr)

def cstr(elf, loads, addr):
    raw = read_ram(elf, loads, addr, 128).split(b'\x00')[0]
    for codec in ('ascii', 'shift_jis'):
        try:
            return raw.decode(codec)
        except UnicodeDecodeError:
            continue
    return raw.decode('shift_jis', errors='replace')

def menu_table(elf, loads, offset, count):
    main = loads[0]
    addr = main['vaddr'] + offset - main['offset']
    raw = read_ram(elf, loads, addr, count * 4)
    values = struct.unpack('<%dI' % count, raw)
    return {'file_offset': offset, 'address': addr,
            'labels': [{'address': v, 'text': cstr(elf, loads, v)} for v in values]}

def main():
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument('source', type=Path, help='User-supplied retail PS2 ISO or its SLPM_663.01 ELF')
    a.add_argument('--json', type=Path, help='Optional JSON findings output (no game data)')
    args = a.parse_args()
    elf, files, disc_file = load_input(args.source)
    info = elf_summary(elf)
    if info['machine'] != 8:
        raise ValueError('Expected MIPS ELF')
    menus = {k: menu_table(elf, info['loads'], *v) for k, v in MENUS.items()}
    probes = []
    for addr, expected in PATCH_PROBES.items():
        actual = u32(read_ram(elf, info['loads'], addr, 4), 0)
        probes.append({'ram': addr, 'expected_unmodified': expected, 'actual': actual,
                       'matches_unmodified': actual == expected})
    table_string = b'cdrom0:\\IBARAR.TBL;1'
    offsets = []
    start = 0
    while True:
        at = elf.find(table_string, start)
        if at < 0: break
        offsets.append(at)
        start = at + len(table_string)
    result = {'input': args.source.name, 'elf': info, 'iso_boot_file': disc_file,
              'iso_file_list': files, 'menu_tables': menus, 'boot_resource_table_offsets': offsets,
              'known_code_points': CODE_POINTS, 'unmodified_patch_probes': probes,
              'notes': [
                  'Code points are inspection locations, not proven safe patch hooks.',
                  'Menu table labels do not establish where artwork lives or whether gameplay engines are shared.',
                  'Kuro arcade assets/logic are not established to exist in the retail ISO.',
                  'No ISO or ELF modifications performed.'
              ]}
    print('Ibara Complete: read-only audit')
    print('Input:', args.source)
    print('ELF SHA256:', info['sha256'])
    print('Entry: 0x%08X, ELF bytes: %d' % (info['entry'], info['file_bytes']))
    for x in info['loads']:
        print('LOAD vaddr=0x%08X offset=0x%X file=0x%X mem=0x%X' % (x['vaddr'], x['offset'], x['file_bytes'], x['memory_bytes']))
    if disc_file:
        print('ISO boot ELF extent LBA:', disc_file['lba'])
        print('Matches prior 240p project LBA:', disc_file['lba'] == EXPECTED_ISO_ELF_LBA_FROM_PRIOR_PATCH)
        print('Disc file list:')
        for f in files: print('  %-48s  LBA=%-8d size=%d' % (f['path'], f['lba'], f['bytes']))
    for key, table in menus.items():
        print('%s @ file 0x%X => %s' % (key, table['file_offset'],
              ', '.join(x['text'] for x in table['labels'])))
    print('IBARAR.TBL reference file offsets:', ', '.join('0x%X' % x for x in offsets) or 'not found')
    print('Patch probes matching original words: %d/%d' % (sum(x['matches_unmodified'] for x in probes), len(probes)))
    if args.json:
        args.json.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf8')
        print('Wrote:', args.json)

if __name__ == '__main__':
    main()
