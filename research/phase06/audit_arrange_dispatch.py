#!/usr/bin/env python3
"""Read-only structural verification of retail Ibara PS2 player-state dispatch.

Requires the user's own unmodified Japanese SLPM_663.01 or 2048-sector ISO.
Reports only addresses, machine-code words, summaries and SHA256; no game data.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

EXPECTED_SHA256 = '263d3079dee66af82815219351553075340a4d9f42aceaa7bb8ef2bfb812ffac'
EXPECTED_ELF_SIZE = 2329648
ELF_LBA = 1919173
ELF_OFFSET = 0x80
LOAD_ADDRESS = 0x00100000
TABLE_ADDRESS = 0x00212F40
STATES = 33

# Static MIPS instructions checked individually against the verified retail ELF.
CHECKS = {
    'dispatch_front_0x139c80': (0x00139C80, 0x0004343C), # dsll32 $a2,$a0,0x10
    'dispatch_front_table_base': (0x00139CA4, 0x24422F40), # addiu $v0,$v0,0x2f40
    'dispatch_front_indirect_jr': (0x00139CC0, 0x00400008),
    'dispatch_second_table_base': (0x00139CF4, 0x24422F40),
    'dispatch_second_indirect_jr': (0x00139D10, 0x00400008),
    'arrange_action_prologue': (0x00139850, 0x27BDFFB0),
    'player_stride_step1': (0x0013987C, 0x00111880),
    'player_stride_step2': (0x00139880, 0x00711821),
    'player_stride_step3': (0x00139884, 0x000318C0),
    'player_stride_step4': (0x00139888, 0x00711821),
    'player_stride_step5': (0x0013988C, 0x00038100),
    'input_bit_0x40': (0x001398E4, 0x30420040),
    'input_bit_0x80': (0x001399A0, 0x30420080),
    'input_bit_0x100': (0x00139A58, 0x30630100),
    'mode_conditional_read': (0x001398CC, 0x8F829254),
}


def load_elf(path: Path) -> bytes:
    if path.suffix.lower() == '.iso':
        with path.open('rb') as f:
            f.seek(ELF_LBA * 2048)
            data = f.read(EXPECTED_ELF_SIZE)
    else:
        data = path.read_bytes()
    if len(data) != EXPECTED_ELF_SIZE or data[:4] != b'\x7fELF':
        raise ValueError('Expected retail SLPM_663.01 at the known disc LBA or as a standalone ELF')
    return data


def word(elf: bytes, va: int) -> int:
    loc = va - LOAD_ADDRESS + ELF_OFFSET
    if loc < 0 or loc + 4 > len(elf):
        raise ValueError(f'VA {va:08X} outside file-backed ELF')
    return struct.unpack_from('<I', elf, loc)[0]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source', type=Path, help='Unmodified original Ibara (Japan).iso or extracted SLPM_663.01')
    ap.add_argument('--json', type=Path, default=None, help='Save structured report')
    ap.add_argument('--csv', type=Path, default=None, help='Save 33-entry dispatch table as CSV')
    ap.add_argument('--allow-variant', action='store_true', help='Report but do not assert known original retail SHA256')
    args = ap.parse_args()
    elf = load_elf(args.source)
    sha = hashlib.sha256(elf).hexdigest()
    if sha != EXPECTED_SHA256 and not args.allow_variant:
        raise ValueError('Unexpected retail ELF SHA256; refusing to label addresses as verified: ' + sha)

    anchors = []
    for name, (va, expected) in CHECKS.items():
        actual = word(elf, va)
        anchors.append({'label':name, 'ee_address':f'0x{va:08X}',
                        'expected_word':f'0x{expected:08X}', 'actual_word':f'0x{actual:08X}',
                        'matches':actual == expected})
    # This is an authoritative static lookup table, not a proof that every state is reachable.
    state_entries = []
    for state in range(STATES):
        va = TABLE_ADDRESS + state*4
        target = word(elf, va)
        state_entries.append({'state': state,'table_address':f'0x{va:08X}',
                              'handler_address':f'0x{target:08X}',
                              'group': 'interactive' if 1 <= state <= 9 else
                                       'other_0_10_15' if state <= 15 else 'other_16_31' if state <= 31 else 'other_32'})
    expected = [0x139B20] + [0x139850]*9 + [0x139B20]*6 + [0x139050]*16 + [0x138F60]
    entries_match = [x['handler_address'] == f'0x{expected[i]:08X}' for i,x in enumerate(state_entries)]

    # Calls must be decoded from instruction words, not assumed from labels in a disassembly.
    outgoing = []
    for va in range(0x139850,0x139B20,4):
        w = word(elf,va)
        if w >> 26 == 3:  # JAL
            target = ((va + 4) & 0xF0000000) | ((w & 0x03FFFFFF)<<2)
            outgoing.append({'callsite':f'0x{va:08X}', 'target':f'0x{target:08X}'})
    incoming = []
    for i in range(ELF_OFFSET, len(elf)-3, 4):
        w = struct.unpack_from('<I',elf,i)[0]
        if w>>26 == 3:
            va = LOAD_ADDRESS + (i - ELF_OFFSET)
            target = ((va+4)&0xF0000000) | ((w&0x03FFFFFF)<<2)
            if target == 0x139850:
                incoming.append(f'0x{va:08X}')

    result = {
        'source':args.source.name, 'elf_sha256':sha, 'retail_sha256_matches':sha == EXPECTED_SHA256,
        'anchors':anchors, 'all_anchors_match': all(a['matches'] for a in anchors),
        'dispatch_table_ee_address':f'0x{TABLE_ADDRESS:08X}',
        'dispatch_table_elf_offset':f'0x{TABLE_ADDRESS-LOAD_ADDRESS+ELF_OFFSET:08X}',
        'table_matches_reference':all(entries_match),
        'handler_histogram':dict(sorted(Counter(x['handler_address'] for x in state_entries).items())),
        'entries':state_entries, 'action_routine':{
            'address':'0x00139850',
            'incoming_direct_jal':incoming,
            'outgoing_jal':outgoing,
            'verified_input_bit_masks':['0x40','0x80','0x100'],
            'player_record_base':'0x0045C380',
            'player_record_stride':0x290,
            'note':'Handler for several player states; flags/behavior require runtime confirmation, not a ready Black Label patch.'}}
    if not result['all_anchors_match'] or not result['table_matches_reference']:
        raise ValueError('Static verification failed; no report marked as verified')
    print('Ibara PS2 retail static dispatch audit — PASS')
    print('ELF SHA256:',sha)
    print('Player state table: 33 entries, EE',hex(TABLE_ADDRESS),'| all reference entries match')
    print('Targets:',result['handler_histogram'])
    print('Input flag masks: 0x40, 0x80, 0x100 | player record stride 0x290')
    print('Direct JAL into 0x139850:',len(incoming),'(function-pointer dispatch, not evidence of no callers)')
    print('Outgoing calls:',', '.join(f"{x['callsite']}=>{x['target']}" for x in outgoing))
    if args.json:
        args.json.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print('Wrote',args.json)
    if args.csv:
        import csv
        with args.csv.open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f, fieldnames=list(state_entries[0]))
            writer.writeheader();writer.writerows(state_entries)
        print('Wrote',args.csv)

if __name__ == '__main__':
    main()
