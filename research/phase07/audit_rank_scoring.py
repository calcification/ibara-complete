#!/usr/bin/env python3
"""Read-only SLPM-66301 PS2 Ibara rank/score structural audit.

Usage: python audit_rank_scoring.py SLPM_663.01 --json report.json --csv callsites.csv
   or: python audit_rank_scoring.py 'Ibara (Japan).iso' --json report.json
Only supports the exact original 2006 Japanese executable; no writes to input.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import struct
from pathlib import Path

ORIGINAL_SHA256 = '263d3079dee66af82815219351553075340a4d9f42aceaa7bb8ef2bfb812ffac'
ELF_SIZE = 2329648
ELF_LBA = 1919173
ELF_LOAD_OFFSET = 0x80
LOAD_ADDR = 0x00100000
SEGMENT_BYTES = 0x238A00
GP = 0x0033FCF0
RANK_VALUE = GP - 0x6E3C
RANK_MAX = GP - 0x6E44
MODE_FLAG = GP - 0x6DAC
PLAYER1_BASE = 0x0045C380
PLAYER_STRIDE = 0x290
RANK_UP = 0x00129DC0  # adds to *stored* value -> lower visual rank
RANK_DOWN = 0x00129DF0  # subtracts -> higher visual rank

# Manually transcribed opcode fingerprints, independent of file loaded at runtime.
# All words are little-endian from the user's original retail ELF.
EXPECTED_WORDS = {
 0x0012CC14:0x8F889254, 0x0012CC18:0x15000018,
 0x0012CC80:0xAF8091C0, 0x0012CC84:0x3464FFFF,
 0x0012CC88:0xAF8091C8, 0x0012CC8C:0xAF8491BC,
 0x0012CC90:0xAF8491C4,
 0x00129518:0x8F8491C4, 0x0012951C:0x3C0300FF,
 0x00129520:0x3465FFFF, 0x00129530:0x00A41823,
 0x00129534:0x00032A02,
 0x00129DCC:0x8F8591C4, 0x00129DD0:0x8F8391BC,
 0x00129DD4:0x00A42021, 0x00129DE0:0xAF8491C4,
 0x00129DE4:0xAF8391C4, 0x00129DFC:0x8F8591C4,
 0x00129E00:0x0085082B, 0x00129E20:0x10000003,
 0x00129E28:0x00A41823, 0x00129E2C:0xAF8391C4,
 0x0012F6A8:0x8F829254, 0x0012F6CC:0x8E030008,
 0x0012F6D4:0x2442BFD0, 0x0012F6E0:0x0C04A77C,
 0x0012F6E4:0x8C440000, 0x0012F6F0:0x8E030008,
 0x0012F6F8:0x2442BFD0, 0x0012F704:0x8C420000,
 0x0012F708:0x0C04A770, 0x0012F70C:0x00022280,
 0x00139010:0x90630000, 0x00139014:0x30630007,
 0x00139020:0x0C04A770, 0x00139024:0x8C440000,
 0x0012C388:0x8E840280,
 0x0012A91C:0x8E220280, 0x0012A928:0x2442000A,
 0x0012A930:0xAE220280, 0x0012ABC8:0x8E220280,
 0x0012ABD4:0x2442000A, 0x0012ABDC:0xAE220280,
 0x0012AC20:0x8E230280, 0x0012AC24:0x00621821,
 0x0012AC2C:0xAE230280, 0x0012E4EC:0x8C620280,
 0x0012E504:0xAC620280, 0x0013ABE0:0x8E230280,
 0x0013ABE4:0x8E240284, 0x0013ABF4:0x8F83917C,
 0x0013ABFC:0xAE230284, 0x0013AC10:0x24620001,
 0x0013AC1C:0xA222025A, 0x0013AC54:0x3C030098,
 0x0013AC58:0x34639680, 0x0013AC60:0xAE230284,
 0x0013E294:0x3C040021, 0x0013E29C:0x24843540,
 0x0013E2B0:0x8C840000,
}

def elf_bytes(path: Path) -> tuple[bytes, str]:
    with path.open('rb') as f:
        header = f.read(2048)
        if header[:4] == b'\x7fELF':
            f.seek(0)
            b = f.read(ELF_SIZE + 1)
            if len(b) != ELF_SIZE:
                raise ValueError('ELF size mismatch; expected %d' % ELF_SIZE)
            source = 'elf'
        elif len(header) >= 2048:
            f.seek(16 * 2048 + 1)
            if f.read(5) != b'CD001':
                raise ValueError('Not an ELF or ISO9660 image')
            f.seek(ELF_LBA * 2048)
            b = f.read(ELF_SIZE)
            if len(b) != ELF_SIZE or b[:4] != b'\x7fELF':
                raise ValueError('ISO does not contain the expected ELF at LBA %d' % ELF_LBA)
            source = 'iso'
        else:
            raise ValueError('Not an ELF or a compatible ISO9660 image')
    return b, source

def word(b:bytes,va:int) -> int:
    o = va - LOAD_ADDR + ELF_LOAD_OFFSET
    if o < ELF_LOAD_OFFSET or o + 4 > len(b) or va & 3:
        raise ValueError('ELF address out of range: 0x%08X' % va)
    return struct.unpack_from('<I',b,o)[0]

def literal_table(b:bytes,va:int,n:int) -> list[int]:
    return [word(b,va+4*i) for i in range(n)]

def classify_call(a:int) -> str:
    if 0x12F000 <= a < 0x12FD00: return 'item-or-pickup-neighborhood (requires caller tracing)'
    if 0x138F00 <= a <= 0x139050: return 'player-stock path'
    if 0x13AD00 <= a < 0x13B500: return 'player-or-increment neighborhood'
    if 0x133000 <= a < 0x134300: return 'gameplay neighborhood'
    return 'other, needs classification'

def delay_argument(ins:int) -> str:
    # An instruction in a MIPS JAL delay slot executes *before* the call.
    op=(ins>>26)&63;rt=(ins>>16)&31;rs=(ins>>21)&31;imm=ins&65535
    simm=imm-65536 if imm&0x8000 else imm
    if op==15 and rt==4: return 'a0=0x%08X (lui)' % (imm<<16)
    if op==9 and rt==4 and rs==0: return 'a0=%d (addiu)' % simm
    if op==0 and (ins&63)==0 and ((ins>>11)&31)==4:
        return 'a0=register-shifted by %d' % ((ins>>6)&31)
    if op==35 and rt==4: return 'a0=memory load, base r%d offset %d' % (rs,simm)
    return 'depends on earlier register state'

def find_calls(b:bytes) -> list[dict]:
    out=[]
    for i in range(0, SEGMENT_BYTES, 4):
        ins=struct.unpack_from('<I',b,ELF_LOAD_OFFSET+i)[0]
        if ins >> 26 != 3: continue
        address=LOAD_ADDR+i
        target=((address+4)&0xF0000000) | ((ins&0x03FFFFFF)<<2)
        if target not in (RANK_UP,RANK_DOWN):continue
        nxt=struct.unpack_from('<I',b,ELF_LOAD_OFFSET+i+4)[0] if i+4 < SEGMENT_BYTES else 0
        out.append({'callsite':'0x%08X'%address,
                    'target':'0x%08X'%target,
                    'effect_on_stored_rank':'increase (less difficulty)' if target==RANK_UP else 'decrease (more difficulty)',
                    'delay_slot_opcode':'0x%08X'%nxt,
                    'a0_at_call':delay_argument(nxt),
                    'neighborhood':classify_call(address)})
    return out

def analyze(b:bytes,source:str)->dict:
    digest=hashlib.sha256(b).hexdigest()
    if digest!=ORIGINAL_SHA256:raise ValueError('Executable SHA256 does not match original retail edition: '+digest)
    errors=['0x%08X: expected %08X, got %08X'%(a,e,word(b,a)) for a,e in EXPECTED_WORDS.items() if word(b,a)!=e]
    if errors:raise ValueError('Instruction fingerprints failed: '+'; '.join(errors[:6]))
    calls=find_calls(b)
    down=sum(c['target']=='0x%08X'%RANK_DOWN for c in calls)
    up=sum(c['target']=='0x%08X'%RANK_UP for c in calls)
    if (down,up)!=(56,2):raise ValueError('Unexpected rank-call pattern: down=%d up=%d'%(down,up))
    return {
      'source_type':source,'elf_sha256':digest,'checks':{'fingerprinted_instructions':len(EXPECTED_WORDS),'rank_decrement_direct_calls':down,'rank_increment_direct_calls':up},
      'address_map':{'gp':'0x%08X'%GP,'mode_flag':'0x%08X'%MODE_FLAG,'stored_rank':'0x%08X'%RANK_VALUE,'rank_ceiling':'0x%08X'%RANK_MAX,
                     'p1_score':'0x%08X'%(PLAYER1_BASE+0x280),'p2_score':'0x%08X'%(PLAYER1_BASE+PLAYER_STRIDE+0x280),
                     'p1_extend_threshold':'0x%08X'%(PLAYER1_BASE+0x284),'p2_extend_threshold':'0x%08X'%(PLAYER1_BASE+PLAYER_STRIDE+0x284),
                     'p1_stock':'0x%08X'%(PLAYER1_BASE+0x25A),'p2_stock':'0x%08X'%(PLAYER1_BASE+PLAYER_STRIDE+0x25A)},
      'tables':{'item_rank_delta_0x20BFD0_first_four':literal_table(b,0x20BFD0,4),
                'stock_indexed_rank_relief_0x213070_eight':literal_table(b,0x213070,8),
                'extend_threshold_candidates_0x213540_seven':literal_table(b,0x213540,7)},
      'rank_calls':calls,
      'interpretive_cautions':['Subtraction of stored rank raises displayed difficulty; zero stored rank is the hardest.',
       'The item-rank lookup at 0x20BFD0 is indexed from a runtime item record. Do not label the exact item types without further proof.',
       'The stock-dependent rank-relief table is identified; the event calling it must still be characterized.',
       'Exact medal scoring values and Kuro XTC are not established by this static PS2 audit.',
       'MIPS callsite addresses and CV1000 SH-3 addresses are not interchangeable.']}

def run(path:Path, json_file:Path|None=None, csv_file:Path|None=None)->dict:
    b,source=elf_bytes(path)
    result=analyze(b,source)
    if json_file: json_file.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    if csv_file:
        with csv_file.open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(result['rank_calls'][0]));w.writeheader();w.writerows(result['rank_calls'])
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input',type=Path,help='Original SLPM_663.01 ELF or original ISO')
    ap.add_argument('--json',type=Path,help='Write JSON report')
    ap.add_argument('--csv',type=Path,help='Write callsite CSV')
    opts=ap.parse_args()
    try:r=run(opts.input,opts.json,opts.csv)
    except (OSError,ValueError) as exc:ap.error(str(exc))
    print('PASS: %s; SHA256 %s'%(r['source_type'],r['elf_sha256']))
    print('Verified %d instructions; %d calls increasing stored rank; %d calls decreasing stored rank.'%(r['checks']['fingerprinted_instructions'],r['checks']['rank_increment_direct_calls'],r['checks']['rank_decrement_direct_calls']))
    print('Rank RAM:',r['address_map']['stored_rank'],'Mode flag:',r['address_map']['mode_flag'])

if __name__=='__main__':main()
