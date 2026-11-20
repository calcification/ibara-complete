#!/usr/bin/env python3
"""Read-only Ibara PS2 retail item/medal dispatch audit.

Only accepts the original Japanese SLPM_663.01 ELF (including inside the original ISO).
The report is a static code/data audit, not gameplay verification.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, struct
from pathlib import Path

ELF_SIZE = 2329648
ELF_LBA = 1919173
LOAD = 0x100000
SEGMENT_OFFSET = 0x80
ELF_SHA256 = '263d3079dee66af82815219351553075340a4d9f42aceaa7bb8ef2bfb812ffac'
P1 = 0x0044c380
P2 = P1 + 0x290
SCORE_OFF = 0x280
HANDLER_TABLE = 0x0020bf60
META_TABLE = 0x0020be80
MEDAL_RANK_TABLE = 0x0020bf80
SCORE_ITEM_RANK_TABLE = 0x0020bfd0

HANDLERS = [
    0x0012fb00, 0x0012edc0, 0x0012f400, 0x0012f7b0,
    0x0012fa10, 0x0012f570, 0x0012f930, 0x0012f680,
]
META_PTRS = [0x208790,0x209700,0x208920,0x20b100,0x208ab0,0x208c40,0x208600,0x20bd00]
META_STATE_PTRS = [0x337f00,0x337f20,0x337f08,0x337f28,0x337f10,0x337f18,0x337ef8,0x337f30]
REWARD_SAMPLE_COUNTS = [1, 8, 1, 19, 1, 1, 1, 8]
EXPECTED_REWARDS = [
    [100], [10000] * 8, [500],
    list(range(100, 1001, 100)) + list(range(2000,10001,1000)),
    [1000], [5000], [10000], [100,200,400,800,100,200,400,800],
]
# Each (VA, raw 32-bit LE instruction) is an independent opcode fingerprint.
EXPECTED_OPCODES = {
    0x0012a984:0x3c040045, 0x0012a98c:0x2484c380,
    0x0012ec4c:0x3c050045, 0x0012ec50:0x24a5c600,
    0x0012f6cc:0x8e030008, 0x0012f6d4:0x2442bfd0,
    0x0012f708:0x0c04a770, 0x0012f70c:0x00022280,
}
JAL_EDGES = {
  0x0012a61c:0x0012fd00,  # collision loop -> type dispatcher
  0x0012f840:0x0012ebf0,  # medal handler -> generic reward
  0x0012f720:0x0012ebf0,  # score-item handler -> generic reward
  0x0012f81c:0x00129df0,  # medal Arcade difficulty
  0x0012f834:0x00129df0,  # medal Arrange difficulty
  0x0012f6e0:0x00129df0,  # score-item Arcade difficulty
  0x0012f708:0x00129dc0,  # score-item Arrange relief
  0x0012ac18:0x00134e90,  # dynamic award: maximum of two fields
}
LABELS = ['Small P?','Option?','Bomb fragment?','Medal (confirmed scoring)','Large P?','Full bomb?','1UP?','Score item (consistent with arcade mapping)']


def extract_elf(path: Path) -> tuple[bytes,str]:
    with path.open('rb') as f:
        hdr = f.read(32)
        if hdr[:4] == b'\x7fELF':
            if path.stat().st_size != ELF_SIZE:
                raise ValueError('ELF size does not match the original Japanese release')
            f.seek(0); blob=f.read()
            source='ELF'
        else:
            f.seek(16*2048+1)
            if f.read(5) != b'CD001':
                raise ValueError('Not a recognized PS2 ELF or ISO9660 image')
            f.seek(ELF_LBA*2048)
            blob=f.read(ELF_SIZE)
            source='ISO'
    if len(blob) != ELF_SIZE or blob[:4] != b'\x7fELF':
        raise ValueError('Retail ELF not found at expected location')
    return blob,source


def word(blob: bytes, va: int) -> int:
    off=va-LOAD+SEGMENT_OFFSET
    if off < SEGMENT_OFFSET or off + 4 > len(blob) or va & 3:
        raise ValueError('Illegal ELF data VA 0x%08X' % va)
    return struct.unpack_from('<I',blob,off)[0]


def check(actual, expected, desc):
    if actual != expected:
        raise ValueError('%s: %r != %r' % (desc, actual, expected))


def jal_target(ins:int, addr:int)->int:
    if (ins>>26) != 3:
        raise ValueError('Not JAL at 0x%08X: 0x%08X' % (addr,ins))
    return ((addr+4)&0xf0000000)|((ins & 0x03ffffff)<<2)


def audit(blob:bytes, verify_sha:bool=True)->dict:
    sha=hashlib.sha256(blob).hexdigest()
    if verify_sha:check(sha,ELF_SHA256,'Retail ELF SHA-256')
    table=[word(blob,HANDLER_TABLE+4*i) for i in range(8)]
    check(table,HANDLERS,'Eight item dispatch targets')
    ptrs=[word(blob,META_TABLE+8*i) for i in range(8)]
    check(ptrs,META_PTRS,'Eight scoring metadata pointers')
    states=[word(blob,META_TABLE+8*i+4) for i in range(8)]
    check(states,META_STATE_PTRS,'Eight scoring state pointers')
    for a,ins in EXPECTED_OPCODES.items():check(word(blob,a),ins,'Instruction at 0x%08X' % a)
    for a,dest in JAL_EDGES.items():
        check(jal_target(word(blob,a),a),dest,'JAL at 0x%08X' % a)
    # The lookup table is loaded through the stack at 0x12FD18..0x12FD68;
    # the selected pointer is called by JALR at 0x12FDA4.
    check(word(blob,0x12fda4),0x0040f809,'Type-dispatch JALR $v0')
    medals=[word(blob,ptrs[3]+16*i+4) for i in range(19)]
    check(medals,EXPECTED_REWARDS[3],'19 medal rewards')
    medrank=[word(blob,MEDAL_RANK_TABLE+4*i) for i in range(19)]
    check(medrank,[256]*9+[1024]*9+[4096],'19 medal Arcade rank deltas')
    scorank=[word(blob,SCORE_ITEM_RANK_TABLE+4*i) for i in range(4)]
    check(scorank,[256,512,768,1024],'Four score-item rank deltas')
    # 0x134E90: slt $at,$a1,$a0; movz $a0,$a1,$at -> max(a0,a1).
    check(word(blob,0x134e90),0x00a4082a,'Max helper SLT')
    check(word(blob,0x134e94),0x00a1200a,'Max helper MOVZ')
    rows=[]
    for i,p in enumerate(ptrs):
        rewards=[word(blob,p+16*k+4) for k in range(REWARD_SAMPLE_COUNTS[i])]
        check(rewards,EXPECTED_REWARDS[i],'Reward entries for type %d'%i)
        rows.append({'type_id':i,'tentative_label':LABELS[i], 'handler':'0x%08X'%table[i],
                     'score_metadata':'0x%08X'%p,'metadata_state':'0x%08X'%states[i],
                     'verified_reward_samples':rewards})
    medal_rows=[{'medal_level':i+1,'score_points':p,'arcade_rank_stored_delta_down':medrank[i],
        'arrange_rank_stored_delta_down':i<<17} for i,p in enumerate(medals)]
    return {'status':'static retail ELF verification; not gameplay tested','elf_sha256':sha,
        'player1_base_corrected':'0x%08X'%P1,'player2_base_corrected':'0x%08X'%P2,
        'player1_score_corrected':'0x%08X'%(P1+SCORE_OFF),
        'player2_score_corrected':'0x%08X'%(P2+SCORE_OFF),
        'collision_to_dispatch':'0x0012A61C -> 0x0012FD00',
        'dispatcher_uses_record_field':'+0x04 (item type ID)',
        'award_uses_record_field':'+0x08 (reward/level index)',
        'generic_award':'0x0012EBF0','handler_table':'0x%08X'%HANDLER_TABLE,
        'score_metadata_table':'0x%08X'%META_TABLE,
        'types':rows,'medals':medal_rows,'score_item_rank_deltas':scorank,
        'dynamic_enemy_reward_max_helper':'0x00134E90',
        'bullet_cancellation':'not established; no claim of a complete tracing path'}


def main()->None:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('image',type=Path,help='Original SLPM_663.01 ELF or Ibara (Japan).iso')
    ap.add_argument('--json',type=Path,default=None)
    ap.add_argument('--csv',type=Path,default=None)
    ap.add_argument('--medal-csv',type=Path,default=None)
    args=ap.parse_args()
    blob,source=extract_elf(args.image)
    report=audit(blob);report['input_kind']=source
    if args.json:args.json.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    if args.csv:
        with args.csv.open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=report['types'][0].keys());w.writeheader();w.writerows(report['types'])
    if args.medal_csv:
        with args.medal_csv.open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=report['medals'][0].keys());w.writeheader();w.writerows(report['medals'])
    print('PASS: %s; 8 pickup handlers; 19 medals; 8 code edges; retail SHA-256 matches' % source)
    print('Corrected score address P1=%s P2=%s' % (report['player1_score_corrected'],report['player2_score_corrected']))
    print('No game files modified.')

if __name__=='__main__':main()
