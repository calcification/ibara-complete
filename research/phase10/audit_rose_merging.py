#!/usr/bin/env python3
"""Ibara Complete Phase 10: static rose-item merging + projectile producer audit.

Usage:
  python audit_rose_merging.py SLPM_663.01
  python audit_rose_merging.py 'Ibara (Japan).iso' --json report.json --csv anchors.csv

READ ONLY: no patches, no copyrighted content in outputs. Requires Python 3.10+;
stdlib only. Supports this exact unmodified Japanese SLPM-66301 retail ELF or ISO.
Static control flow does NOT prove in-game success rates or game performance.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
from pathlib import Path

ELF_SHA256 = '263d3079dee66af82815219351553075340a4d9f42aceaa7bb8ef2bfb812ffac'
ELF_SIZE = 2_329_648
ISO_ELF_LBA = 1_919_173
SECTOR = 2048
EE_VADDR_BASE = 0x00100000
EE_FILE_BASE = 0x80

# This table is a whitelist of instruction fingerprints extracted from the
# user's original binary. It is *not* executable code or a ROM replacement.
# The report tests all words for the supported retail revision.
ANCHORS = {
  0x0011A580:0x27BDFFE0,
  0x0011A58C:0x3C020045,
  0x0011A5A0:0x2442EA40,
  0x0011A5DC:0x28C20080,
  0x0011A5E4:0x24630050,
  0x0011A5F4:0x10400079,
  0x0011A6AC:0xAD800004,
  0x0011A7BC:0x24E2FFFF,
  0x0011A7D4:0x1000FF85,
  0x0011A7D8:0x24020001,
  0x0012EA10:0x27BDFFC0,
  0x0012EA44:0x3C030045,
  0x0012EA4C:0x24633A40,
  0x0012EA70:0x108E0047,
  0x0012EA78:0x8DCC0000,
  0x0012EA7C:0x11800044,
  0x0012EA84:0x8DCF0004,
  0x0012EA88:0x8C8C0004,
  0x0012EA8C:0x15EC0040,
  0x0012EA94:0x8DCF0008,
  0x0012EA98:0x8C8C0008,
  0x0012EA9C:0x15EC003C,
  0x0012EAAC:0x12600038,
  0x0012EAD8:0x07200039,
  0x0012EAE4:0x032F082A,
  0x0012EAE8:0x10200025,
  0x0012EAF4:0x07000034,
  0x0012EB04:0x030F082A,
  0x0012EB08:0x1020001D,
  0x0012EB10:0x8C850008,
  0x0012EB18:0x24A50001,
  0x0012EB1C:0xAC850008,
  0x0012EB64:0xAC830030,
  0x0012EB68:0xADC00000,
  0x0012EB6C:0x8DC30054,
  0x0012EB70:0x8C850054,
  0x0012EB74:0x00A31821,
  0x0012EB78:0x10000015,
  0x0012EB7C:0xAC830054,
  0x0012EB90:0x254A0001,
  0x0012EB94:0x294C0100,
  0x0012EB98:0x1580FFB5,
  0x0012EB9C:0x25CE0058,
  0x0012EBA8:0x000B593E,
  0x0012EBAC:0x1560FFA8,
  0x0012F730:0x8E040008,
  0x0012F734:0x8E020054,
  0x0012F738:0x00041880,
  0x0012F73C:0x00641821,
  0x0012F740:0x00031840,
  0x0012F744:0x2463001E,
  0x0012F748:0x00433818,
  0x001304E0:0x27BDFF90,
  0x00130594:0x24040004,
  0x0013059C:0x24020007,
  0x001305B4:0xAE030000,
  0x001305B8:0x0C0443F8,
  0x001305BC:0xAE020004,
  0x001305C0:0x24420004,
  0x001305C8:0xAE020008,
  0x001307B0:0x0C04C228,
  0x00130810:0x24030007,
  0x00130814:0x16830018,
  0x0013081C:0x8F8291C4,
  0x00130820:0x3C030100,
  0x00130824:0x00621023,
  0x00130828:0x00021402,
  0x0013082C:0xAE020054,
  0x0013084C:0x2402012C,
  0x00130850:0xAE020054,
  0x001308FC:0xAE050004,
  0x00130900:0x8F839254,
  0x00130904:0x10600068,
  0x00130AA8:0x0C0443F8,
  0x00130AAC:0x24040007,
  0x00130AB4:0xAE020008,
  0x00132BC0:0x27BDFFE0,
  0x00132DC0:0x8E030008,
  0x00132DC4:0x28630003,
  0x00132DC8:0x14600025,
  0x00132E60:0x0C04BA84,
  0x00132E64:0x0200202D,
}

GROUPS = {
  'type7_update': [0x00132BC0,0x00132DC0,0x00132DC4,0x00132DC8,
                   0x00132E60,0x00132E64],
  'merge_guards': [0x0012EA10,0x0012EA44,0x0012EA4C,0x0012EA70,
                   0x0012EA78,0x0012EA7C,0x0012EA84,0x0012EA88,
                   0x0012EA8C,0x0012EA94,0x0012EA98,0x0012EA9C,
                   0x0012EAAC,0x0012EAD8,0x0012EAE4,0x0012EAE8,
                   0x0012EAF4,0x0012EB04,0x0012EB08],
  'merge_commit': [0x0012EB10,0x0012EB18,0x0012EB1C,0x0012EB64,
                   0x0012EB68,0x0012EB6C,0x0012EB70,0x0012EB74,
                   0x0012EB78,0x0012EB7C,0x0012EB90,0x0012EB94,
                   0x0012EB98,0x0012EB9C,0x0012EBA8,0x0012EBAC],
  'score_multiplier': [0x001307B0,0x00130810,0x00130814,0x0013081C,
                   0x00130820,0x00130824,0x00130828,0x0013082C,
                   0x0013084C,0x00130850,0x0012F730,0x0012F734,
                   0x0012F738,0x0012F73C,0x0012F740,0x0012F744,
                   0x0012F748],
  'randomized_initializers': [0x001304E0,0x00130594,0x0013059C,
                   0x001305B4,0x001305B8,0x001305BC,0x001305C0,
                   0x001305C8,0x001308FC,0x00130900,0x00130904,
                   0x00130AA8,0x00130AAC,0x00130AB4],
  'projectile_producer': [0x0011A580,0x0011A58C,0x0011A5A0,
                   0x0011A5DC,0x0011A5E4,0x0011A5F4,0x0011A6AC,
                   0x0011A7BC,0x0011A7D4,0x0011A7D8],
}

EXPECTED_UPDATE_TABLE = [
    0x001323D0, 0x001323D0, 0x001323D0, 0x001322F0,
    0x001323D0, 0x001323D0, 0x001323D0, 0x00132BC0,
]
UPDATE_TABLE_ADDR = 0x0020BF00
JAL_EDGES = {
  0x00132E60:0x0012EA10,  # type-7 item update -> item merge helper
  0x001307B0:0x001308A0,  # new item -> initializer
  0x001305B8:0x00110FE0,  # alternate item type 7 producer -> RNG
  0x00130AA8:0x00110FE0,  # Arcade item type 7 initializer -> RNG
}


def extract_elf(path:Path) -> tuple[bytes,str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open('rb') as f:
        signature = f.read(4)
        if signature == b'\x7fELF':
            if path.stat().st_size != ELF_SIZE:
                raise ValueError('unrecognized ELF size; only exact unmodified SLPM_663.01 supported')
            f.seek(0)
            return f.read(), 'ELF'
        f.seek(SECTOR*16+1)
        if f.read(5) != b'CD001':
            raise ValueError('input is neither a supported ELF nor a 2048-byte-sector ISO9660 image')
        f.seek(ISO_ELF_LBA*SECTOR)
        elf=f.read(ELF_SIZE)
        if len(elf)!=ELF_SIZE or elf[:4]!=b'\x7fELF':
            raise ValueError('expected retail ELF not found at known ISO LBA')
        return elf,'ISO'


def word(elf:bytes, addr:int) -> int:
    off=EE_FILE_BASE+addr-EE_VADDR_BASE
    if addr%4 or off<EE_FILE_BASE or off+4>len(elf):
        raise ValueError(f'out-of-range EE address 0x{addr:08X}')
    return struct.unpack_from('<I',elf,off)[0]


def jal_target(op:int,addr:int) -> int:
    if op>>26 != 3:
        raise ValueError(f'expected MIPS JAL at 0x{addr:08X}, got 0x{op:08X}')
    return ((addr+4)&0xf0000000) | ((op&0x03ffffff)<<2)


def branch_target(op:int,addr:int)->int:
    """Only B/BEQ/BNE relative branch encodings used in this audit."""
    if (op>>26) not in (4,5):
        raise ValueError(f'not a supported MIPS branch at 0x{addr:08X}')
    displacement=struct.unpack('<h',struct.pack('<H',op&0xffff))[0]
    return addr+4+4*displacement


def rose_points(level:int, accumulated_factor:int) -> int:
    """Raw native Arrange rose award, modulo unsigned 32-bit EE result.

    Distinguish spawn-time factor (clamped 1..300) from the accumulator at +0x54,
    which may be larger than 300 due to merging. This isn't a complete score/HUD model.
    """
    if not 0<=level<=0xffffffff or not 0<=accumulated_factor<=0xffffffff:
        raise ValueError('expected unsigned 32-bit level and factor')
    return ((10*level+30)*accumulated_factor)&0xffffffff


def hypothetical_merge(*, left_level:int, left_factor:int, right_level:int,
                       right_factor:int, same_type:bool=True,
                       both_active:bool=True, overlap:bool=True) -> dict:
    """Model one *successful* type-7 update encounter (NOT general simulation).

    Real code also requires shape pointers, bounding geometry and loop conditions.
    'overlap' is the caller's prevalidated geometry result, not computed here.
    """
    if not all(0<=v<=0xffffffff for v in (left_level,left_factor,right_level,right_factor)):
        raise ValueError('unsigned 32-bit values required')
    can_merge=(left_level<3 and left_level==right_level and same_type and both_active and overlap)
    return dict(merged=can_merge, resulting_level=(left_level+1)&0xffffffff if can_merge else left_level,
                resulting_factor=(left_factor+right_factor)&0xffffffff if can_merge else left_factor,
                right_deactivated=can_merge,
                caveat='geometry and live engine state are not simulated')


def audit_elf(elf:bytes,*,verify_sha:bool=True)->dict:
    if len(elf)!=ELF_SIZE or elf[:4]!=b'\x7fELF':
        raise ValueError('wrong ELF format or size')
    sha=hashlib.sha256(elf).hexdigest()
    if verify_sha and sha!=ELF_SHA256:
        raise ValueError('wrong retail revision or modified ELF: SHA256 mismatch')
    if len(ANCHORS)<60:
        raise ValueError('developer error: insufficient instruction fingerprints')
    for addr,expected in ANCHORS.items():
        actual=word(elf,addr)
        if actual!=expected:
            raise ValueError(f'opcode mismatch at EE 0x{addr:08X}: got 0x{actual:08X}, expected 0x{expected:08X}')
    table=[word(elf,UPDATE_TABLE_ADDR+4*i) for i in range(8)]
    if table != EXPECTED_UPDATE_TABLE:
        raise ValueError('eight-entry type-update dispatch table mismatch')
    for origin,target in JAL_EDGES.items():
        if jal_target(word(elf,origin),origin)!=target:
            raise ValueError(f'call target mismatch at EE 0x{origin:08X}')
    if branch_target(word(elf,0x00132DC8),0x00132DC8)!=0x00132E60:
        raise ValueError('type7 update level-gate branch target mismatch')
    if branch_target(word(elf,0x0012EB78),0x0012EB78)!=0x0012EBD0:
        raise ValueError('merge early-exit target mismatch')
    if branch_target(word(elf,0x0012EB98),0x0012EB98)!=0x0012EA70:
        raise ValueError('item-scan loop target mismatch')
    # 0x12EB78 is unconditional BEQ zero,zero; 0x12EB7C is its DELAY SLOT
    # that writes the accumulated multiplier, then the helper returns.
    if (word(elf,0x0012EB78)>>26)!=4 or ((word(elf,0x0012EB78)>>16)&0x3ff)!=0:
        raise ValueError('successful merge is no longer unconditional one-merge-per-call exit')
    # Verifies 256-item search and 0x58-byte slot stepping, and type-7 update.
    if word(elf,0x0012EB94)!=0x294C0100 or word(elf,0x0012EB9C)!=0x25CE0058:
        raise ValueError('item scan bound or 0x58 stride changed')
    if table[7]!=0x00132BC0:
        raise ValueError('type-7 updater changed')
    cases=[]
    for level,fa,fb in [(0,100,50),(0,300,300),(2,100,50),(3,100,50)]:
        m=hypothetical_merge(left_level=level,left_factor=fa,right_level=level,right_factor=fb)
        cases.append(dict(level_before=level,left_factor_before=fa,right_factor_before=fb,
                          separated_raw_award=(rose_points(level,fa)+rose_points(level,fb))&0xffffffff,
                          merged_raw_award=rose_points(m['resulting_level'],m['resulting_factor']) if m['merged'] else None,
                          **m))
    return {
      'status':'verified STATIC reading of exact unmodified retail ELF; no running PS2 or PCSX2 measurements',
      'elf_sha256':sha,
      'instruction_fingerprints_checked':len(ANCHORS),
      'jal_edges_checked':len(JAL_EDGES),
      'type_update_table_EE':f'0x{UPDATE_TABLE_ADDR:08X}',
      'type_update_targets':[f'0x{x:08X}' for x in table],
      'type_7_updater_EE':'0x00132BC0',
      'type_7_level_gate_EE':'0x00132DC0–0x00132DC8',
      'type_7_merge_call_EE':'0x00132E60',
      'merge_helper_EE':'0x0012EA10',
      'candidate_array_base_EE':'0x00453A40',
      'candidate_stride_bytes':0x58,
      'candidate_count':256,
      'matching_checks':['both item slots active and not same pointer','same +0x04 type','same +0x08 level','shape data present and two-axis overlap'],
      'on_success':['survivor +0x08 level increments by one','absorbed slot +0x00 set to 0','survivor +0x54 += absorbed +0x54 (wrap unsigned 32-bit)','unconditional branch to helper return (at most one merge per call)'],
      'important_limits':['updater only calls merge helper for entering level <3','other item types may also use merge helper; type 7 use is proved','no factor clamp after successful merge','Phase9 score helper limited factor<=300 incorrectly; accumulation can exceed 300'],
      'type_0_projectile_emitter_EE':'0x0011A580 (writes 0 to projectile +0x04 at 0x0011A6AC)',
      'projectile_emitter_note':'type 0 producer verified; weapon identity not yet attributed',
      'randomized_type_7_paths':['0x001305B8 calls 0x00110FE0 with a0=4; stores return+4 at item+0x08','0x00130AA8 calls 0x00110FE0 with a0=7; stores result at item+0x08 on Arcade initializer path'],
      'hypothetical_award_cases':cases,
    }


def csv_anchors(path:Path)->None:
    memberships={a:[] for a in ANCHORS}
    for group,addrs in GROUPS.items():
        for a in addrs:
            memberships.setdefault(a,[]).append(group)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f)
        w.writerow(['EE_address','original_instruction_word','category'])
        for a,op in sorted(ANCHORS.items()):
            w.writerow([f'0x{a:08X}',f'0x{op:08X}',';'.join(memberships[a])])


def main()->None:
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('original_elf_or_iso',type=Path)
    ap.add_argument('--json',type=Path,help='write machine-readable audit results')
    ap.add_argument('--csv',type=Path,help='write original instruction anchors in CSV format')
    args=ap.parse_args()
    data,kind=extract_elf(args.original_elf_or_iso)
    result=audit_elf(data)
    result['source_kind']=kind
    if args.json:
        args.json.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    if args.csv:
        csv_anchors(args.csv)
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    main()
