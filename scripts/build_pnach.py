#!/usr/bin/env python3
"""Generate the low-storage PCSX2 test suite for the original SLPM-66301 revision.

Public-domain/machine-readable recipe only: no commercial ELF or ROM bytes.
Supports a raw retail ELF or original ISO for optional expected-word verification.
No game image is ever written. Python 3.10+, standard library.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import re
import struct
import sys

SERIAL = 'SLPM-66301'
CRC = '420C7FAB'
NAME = f'{SERIAL}_{CRC}.pnach'
ELF_SHA256 = '263d3079dee66af82815219351553075340a4d9f42aceaa7bb8ef2bfb812ffac'
ELF_SIZE = 2329648
ELF_LBA = 1919173
ELF_BASE = 0x00100000
ELF_FILE_OFFSET = 0x80

# Original retail words, derived from user-provided verified patch list.
# These are plain code/data opcodes, not redistributed copyrighted software.
VIDEO_EDITS = [
    (0x001AD250, 0x24050001, 0x24050000),
    (0x001AF11C, 0x24040060, 0x24040000),
    (0x001DD1C0, 0x00000000, 0x00000008),
    (0x001DD1C8, 0x00000000, 0x00000008),
    (0x001DD1D0, 0x000000F0, 0x000000E8),
    (0x001DD1D8, 0x000000F0, 0x000000E8),
    (0x001DD200, 0x00000000, 0x00000008),
    (0x001DD208, 0x00000000, 0x00000008),
    (0x001DD210, 0x000000F0, 0x000000E8),
    (0x001DD218, 0x000000F0, 0x000000E8),
    (0x001DD240, 0x00000000, 0x00000008),
    (0x001DD248, 0x00000000, 0x00000008),
    (0x001DD250, 0x000000F0, 0x000000E8),
    (0x001DD258, 0x000000F0, 0x000000E8),
]
HALFPIXEL_EDITS = [
    (0x001AECD4, 0x24AA7900, 0x24AA78F8),
    (0x001AED3C, 0x26527900, 0x265278F8),
    (0x001AED88, 0x24427900, 0x244278F8),
    (0x001AEDD4, 0x24427900, 0x244278F8),
]
# Phase 8 award table: first medal level, reward in +4 of 16-byte descriptor.
MEDAL_REWARD = (0x0020B104, 0x00000064, 0x00002710)

# The mode/score diagnostic addresses are runtime globals (outside ELF file),
# so they cannot be pre-image checked against an on-disc word. Their meaning
# follows verified Phase 7/8 runtime-referenced address calculations.
TESTS = {
    '240p_core': {
        'title': 'VIDEO / 14-edit 240p nearest and crop',
        'description': '14 core writes and progressive scan verified in PCSX2 2.8.2. CRT shimmer remains open.',
        'phase': 'P01', 'place': 2, 'edits': [(a,v) for a,_,v in VIDEO_EDITS],
    },
    '240p_halfpixel': {
        'title': 'VIDEO / 18-edit 240p plus half-pixel adjustment',
        'description': 'All 18 writes and progressive scan verified in PCSX2 2.8.2. Motion quality remains open.',
        'phase': 'P02', 'place': 2, 'edits': [(a,v) for a,_,v in VIDEO_EDITS+HALFPIXEL_EDITS],
    },
    'score_marker': {
        'title': 'DIAGNOSTIC / P1 score marker 1000000',
        'description': 'Writes P1 score at corrected 0044C600 to 1000000 every vsync. Use a temporary or empty memory card.',
        'phase': 'P03', 'place': 1, 'edits': [(0x0044C600,0x000F4240)],
    },
    'rank_easy': {
        'title': 'DIAGNOSTIC / rank easiest 00FFFFFF',
        'description': 'Holds inverted rank global at easiest value 00FFFFFF. Never enable with rank_hard.',
        'phase': 'P04', 'place': 1, 'edits': [(0x00338EB4,0x00FFFFFF)],
    },
    'rank_hard': {
        'title': 'DIAGNOSTIC / rank hardest 00000000',
        'description': 'Holds inverted rank global at hardest value 00000000. Never enable with rank_easy.',
        'phase': 'P05', 'place': 1, 'edits': [(0x00338EB4,0x00000000)],
    },
    'medal_first_10000': {
        'title': 'DIAGNOSTIC / first medal 10000 points',
        'description': 'Changes only first medal reward table entry from 100 to 10000. Pick up level-0 medal to test.',
        'phase': 'P06', 'place': 2, 'edits': [(MEDAL_REWARD[0],MEDAL_REWARD[2])],
    },
}

HEADER = (
    'gametitle=Ibara (Japan) (SLPM-66301)\n'
    '// Ibara Complete RESEARCH ONLY | original ELF XOR CRC 420C7FAB\n'
    '// PNACH changes EE RAM at runtime; DOES NOT add a BLACK LABEL mode.\n'
    '// Uses the clean retail executable, NOT a pre-patched 240p ELF.\n'
    '// WARNING: Enable ONE test at a time; video tests and rank tests conflict.\n'
    '// See tests/manual/RESULTS_P01_P02.md for the PCSX2 video results.\n'
)


def xor_elf_crc(elf: bytes) -> int:
    crc = 0
    for (word,) in struct.iter_unpack('<I', elf[:len(elf)//4*4]):
        crc ^= word
    return crc


def load_elf(path: Path) -> bytes:
    with path.open('rb') as f:
        if path.suffix.lower() == '.iso':
            f.seek(ELF_LBA*2048)
        data = f.read(ELF_SIZE)
    if len(data) != ELF_SIZE or not data.startswith(b'\x7fELF'):
        raise ValueError('Not original Ibara ELF or readable original ISO')
    actual = hashlib.sha256(data).hexdigest()
    if actual != ELF_SHA256:
        raise ValueError(f'Wrong ELF/ISO revision. SHA256: {actual}. Refusing to validate original-only tests.')
    crc=xor_elf_crc(data)
    if crc != int(CRC, 16):
        raise ValueError(f'Unexpected PCSX2 XOR checksum: {crc:08X}')
    for addr, before, after in VIDEO_EDITS+HALFPIXEL_EDITS+[MEDAL_REWARD]:
        off=addr-ELF_BASE+ELF_FILE_OFFSET
        if off < 0 or off+4>len(data):
            raise AssertionError(f'Anchor out of ELF range: {addr:08X}')
        (found,) = struct.unpack_from('<I',data,off)
        if found!=before:
            raise AssertionError(f'Preimage mismatch @ {addr:08X}: found {found:08X}, expected {before:08X}')
    return data


def block(key: str) -> str:
    info=TESTS[key]
    lines=[f'[Ibara Complete\\{info["phase"]} {info["title"]}]',
           f'description={info["description"]}',
           'author=Ibara Complete Research']
    for addr,value in info['edits']:
        lines.append(f'patch={info["place"]},EE,{addr:08X},word,{value:08X}')
    return '\n'.join(lines)+'\n'


def write_files(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    combo=HEADER+'\n'+'\n'.join(block(key) for key in TESTS)
    (out/NAME).write_text(combo,encoding='utf-8')
    profiles=out/'profiles'
    for key in ['baseline', *TESTS]:
        folder=profiles/key;folder.mkdir(parents=True,exist_ok=True)
        txt=HEADER+'\n' + (block(key) if key!='baseline' else '// Baseline: no EE writes. Check retail behavior unchanged.\n')
        (folder/NAME).write_text(txt,encoding='utf-8')
    check_pnach(combo)
    for p in profiles.glob('*/'+NAME): check_pnach(p.read_text(encoding='utf-8'))


def check_pnach(src: str, min_addr: int = 0x100000):
    if not src.startswith('gametitle=Ibara'):
        raise AssertionError('Bad PNACH header')
    groups=[];seen=set();cur='';entries=[]
    for line in src.splitlines():
        line=line.strip()
        if line.startswith('['):
            if not line.endswith(']'): raise AssertionError('Invalid group')
            cur=line;groups.append(line)
        if not line.startswith('patch='):continue
        m=re.fullmatch(r'patch=([0123]),EE,([0-9A-F]{8}),word,([0-9A-F]{8})',line)
        if not m or not cur: raise AssertionError('Invalid patch syntax/group: '+line)
        p=int(m[1]);addr=int(m[2],16);val=int(m[3],16)
        if addr & 3: raise AssertionError('Unaligned write')
        if not (min_addr<=addr<0x02000000): raise AssertionError('Out-of-bounds EE address')
        if (cur,addr) in seen: raise AssertionError('Duplicate group-address pair')
        seen.add((cur,addr));entries.append((cur,p,addr,val))
    if src.find('patch=')!=-1 and not entries: raise AssertionError('Found patch text but no valid commands')
    return {'groups':len(groups),'writes':len(entries)}


def main():
    parser=argparse.ArgumentParser(description='Create tiny PCSX2 research PNACH patches (no ISO rebuild).')
    parser.add_argument('--verify',metavar='ELF_OR_ISO',type=Path,help='Optional: verify original ELF SHA and all preimage words')
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'pnach')
    args=parser.parse_args()
    if args.verify:
        data=load_elf(args.verify)
        print(f'PASS original ELF, SHA256, PCSX2 XOR CRC {xor_elf_crc(data):08X}, and {len(VIDEO_EDITS)+len(HALFPIXEL_EDITS)+1} patch anchors')
    write_files(args.output)
    stats=check_pnach((args.output/NAME).read_text())
    print(f'Generated {NAME} ({stats["groups"]} selectable groups, {stats["writes"]} total writes) and {len(TESTS)+1} profiles in {args.output}')

if __name__=='__main__':
    try:main()
    except (ValueError, AssertionError) as err:
        print('FAIL:',err,file=sys.stderr)
        raise SystemExit(1)
