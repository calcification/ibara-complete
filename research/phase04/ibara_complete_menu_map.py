#!/usr/bin/env python3
"""Ibara Complete Phase 4: READ-ONLY analysis of SLPM_663.01's top-level selector.

Usage:
  python ibara_complete_menu_map.py "Ibara (Japan).iso" --out menu_report.json
  python ibara_complete_menu_map.py SLPM_663.01 --out menu_report.json
  python ibara_complete_menu_map.py "Ibara (Japan).iso" --sprites sprite_folder

Requires ibara_complete_audit.py from Phase 1 in the same directory.
Option --sprites additionally requires Pillow, only to export original retail TIM2
textures 945 and 946 for personal analysis. Distributing this tool does NOT
include copyrighted game data. This tool never patches the ISO or executable.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
import ibara_complete_audit as retail

ORIGINAL_SHA256 = '263d3079dee66af82815219351553075340a4d9f42aceaa7bb8ef2bfb812ffac'

# The top-level five-entry selector is at 0x1ca42c; NOT the Arcade/Arrange
# submenus at 0x1caa88 / 0x1ccbf4 already analyzed in Phase 1.
ENTRY_LABELS = ['ARCADE MODE', 'ARRANGE MODE', 'GALLERY', 'OPTION', 'EXIT']
SITES = {
    'front_end_caller': 0x00113634,
    'initial_menu_state': 0x001CA2C8,
    'selector_start': 0x001CA42C,
    'move_down_limit': 0x001CA44C,
    'animation_loop_limit': 0x001CA494,
    'label_render_limit': 0x001CA56C,
    'label_render_entry': 0x001CA5EC,
    'sprite_loop_limit': 0x001CA6DC,
    'move_up_wrap_to_last': 0x001CA720,
    'move_down_wrap_to_first': 0x001CA72C,
    'accept_dispatch_start': 0x001CA798,
    'arcade_entry': 0x001CA800,
    'arrange_entry': 0x001CA824,
    'gallery_entry': 0x001CA848,
    'options_entry': 0x001CA860,
    'exit_entry': 0x001CA7E4,
    'top_level_return': 0x001CE780,
}
LIMITS = [0x001CA44C, 0x001CA494, 0x001CA56C, 0x001CA6DC]
DESTINATIONS = {0:(0x001CA800, 'frontend state 2 (Arcade submenu)'),
                1:(0x001CA824, 'frontend state 9 (Arrange submenu)'),
                2:(0x001CA848, 'return value 2 (Gallery request to caller)'),
                3:(0x001CA860, 'frontend state 13 (Option)'),
                4:(0x001CA7E4, 'return value 1 (Exit request)')}
DATA = {
    'five_pair_draw_table': 0x002A90B0,
    'first_animation_array': 0x00500620,
    'second_animation_array': 0x00500640,
    'fade_array': 0x00500660,
}
PDM_IDS = {945: 0x2D20800, 946: 0x2D31000}


def get_word(elf, loads, address):
    return struct.unpack('<I', retail.read_ram(elf, loads, address, 4))[0]


def pointer_data(elf, loads):
    base = DATA['five_pair_draw_table']
    # Values are pointers to 16-byte texture descriptors, in paired entries;
    # beyond the 5th pair starts a different table at 0x002A90E0.
    pairs = []
    for i in range(5):
        a, b = struct.unpack('<II', retail.read_ram(elf, loads, base+8*i, 8))
        pairs.append({'index':i,'first':f'0x{a:08X}','second':f'0x{b:08X}'})
    after = struct.unpack('<4I', retail.read_ram(elf, loads, base+40, 16))
    return pairs, [f'0x{p:08X}' for p in after]


def asset_info(input_path, iso_files):
    matches = {}
    for e in iso_files:
        matches[e['name'].split(';')[0].upper()] = e
    if not all(k in matches for k in ('IBARAR.TBL','IBARAR.PDM')):
        raise ValueError('Disc resource files missing')
    with input_path.open('rb') as fh:
        tbl = matches['IBARAR.TBL']
        pdm = matches['IBARAR.PDM']
        fh.seek(tbl['lba']*2048)
        t = fh.read(tbl['bytes'])
        if t[:4] != b'TBL\x04' or len(t) != 18100:
            raise ValueError('Unexpected retail IBARAR.TBL revision')
        output = []
        for rid, known_off in PDM_IDS.items():
            off = struct.unpack_from('<I', t, 0x350C + 4*rid)[0]
            if off != known_off: raise ValueError('Unexpected texture offset for resource %d' % rid)
            fh.seek(pdm['lba']*2048 + off)
            h = fh.read(16)
            if h[:4] != b'TIM2':raise ValueError('Resource %d not TIM2' % rid)
            base = 128 if h[5] else 16
            fh.seek(pdm['lba']*2048 + off + base)
            ph = fh.read(24)
            width, height = struct.unpack_from('<HH', ph,20)
            output.append({'id':rid,'pdm_offset':f'0x{off:X}',
                           'tim2_header_present':True,'width':width,'height':height,
                           'image_type':ph[19], 'palette_type':ph[18]&0x1f})
    return output


def export_sprites(input_path, iso_files, output_dir, resource_info):
    from PIL import Image  # optional; not required for metadata audit
    files = {e['name'].split(';')[0].upper():e for e in iso_files}
    pdm = files['IBARAR.PDM']
    output_dir.mkdir(parents=True, exist_ok=True)
    exported=[]
    with input_path.open('rb') as fh:
        for e in resource_info:
            off=int(e['pdm_offset'],16); base=pdm['lba']*2048+off
            fh.seek(base); h=fh.read(16); head_delta=128 if h[5] else 16
            fh.seek(base+head_delta); ph=fh.read(24)
            _, palette_size, image_size, header_size, *_ = struct.unpack_from('<IIIHHBBBBHH',ph,0)
            fh.seek(base+head_delta+header_size)
            raw=fh.read(image_size); clut=fh.read(palette_size)
            if e['image_type'] != 5 or e['palette_type'] != 3:
                raise ValueError('Unsupported menu TIM2 encoding; expected 8bit indexed RGBA palette')
            palette=[(clut[i],clut[i+1],clut[i+2], min(255,clut[i+3]*255//128)) for i in range(0,len(clut),4)]
            # Unswizzle the indexed palette per PS2 CSM1 (unless CSM2 flag).
            if not (ph[18] & 0x80) and len(palette) >= 256:
                for start in range(0,256,32):
                    palette[start+8:start+16],palette[start+16:start+24] = palette[start+16:start+24],palette[start+8:start+16]
            w,hgt=e['width'],e['height']
            pixelbytes=bytearray(w*hgt*4)
            for i,idx in enumerate(raw[:w*hgt]):
                pixelbytes[4*i:4*i+4]=bytes(palette[idx])
            im=Image.frombytes('RGBA',(w,hgt),bytes(pixelbytes))
            output=output_dir / f'IBARAR_resource_{e["id"]}.png'
            im.save(output)
            exported.append(str(output))
    return exported


def make_map(elf, info):
    loads=info['loads']; ops={}
    for title,addr in SITES.items():
        word=get_word(elf,loads,addr)
        ops[title]={'ee_address':f'0x{addr:08X}', 'file_offset':f'0x{addr-0x100000+0x80:07X}', 'word':f'0x{word:08X}'}
    limits=[]
    for a in LIMITS:
        w=get_word(elf,loads,a)
        if (w>>26) != 0x0A or (w&0xffff) != 5:
            raise ValueError(f'0x{a:08X} is not the expected slti ...,5: 0x{w:08X}')
        limits.append({'ee_address':f'0x{a:08X}', 'old_word':f'0x{w:08X}',
                       'possible_six_entries_word':f'0x{(w & 0xffff0000)|6:08X}',
                       'status':'DO NOT APPLY alone: other code/data changes required'})
    # Anchor coordinates: the 5 menu items are seeded at 0xD8,0xB8,0x98,0x78,0x58.
    values=[]
    for a in (0x1CA2E0,0x1CA2F8,0x1CA310,0x1CA328,0x1CA340):
        w=get_word(elf,loads,a)
        if (w & 0xffff0000)!=0x24030000:
            raise ValueError(f'Unexpected anchor initializer 0x{a:X}: 0x{w:X}')
        values.append(w & 0xffff)
    if values!=[0xD8,0xB8,0x98,0x78,0x58]:
        raise ValueError('Unexpected menu item anchor values')
    pairs,following=pointer_data(elf,loads)
    if pairs[-1]['second']!='0x00000000' or following[:2]!=['0x00000000','0x00000000'] or following[2]!='0x00301D50':
        raise ValueError('Unexpected menu graphics table; no safe sixth pointer-pair proposal')
    return {'sites':ops,'limits':limits,'anchor_values':values,
            'candidate_sixth_anchor':0x38,'draw_pairs':pairs,
            'bytes_after_draw_pairs':following,
            'sixth_pointer_pair_addresses':['0x002A90D8','0x002A90DC'],
            'sixth_pointer_pair_original_values':['0x00000000','0x00000000'],
            'note':'The zero pointer-pair fits before an unrelated table at 0x002A90E0; a new graphics descriptor still needs allocation',
            'state_dispatch':[{'index':i, 'label':ENTRY_LABELS[i],
                               'address':f'0x{DESTINATIONS[i][0]:08X}',
                               'result':DESTINATIONS[i][1]} for i in range(5)],
            'array_bases':{k:f'0x{v:08X}' for k,v in DATA.items()},
            'hypothetical_6th_positions':{
                'first':f'0x{DATA["first_animation_array"]+0x14:08X}',
                'second':f'0x{DATA["second_animation_array"]+0x14:08X}',
                'fade':f'0x{DATA["fade_array"]+0x14:08X}'}}


def breakpoint_text():
    lines=['Ibara Complete Phase 4: manually add these as EXECUTION breakpoints in PCSX2',
           'Unmodified retail executable SLPM_663.01 only; no patch is needed.',
           'Avoid relying on hardcoded $gp values; read $gp in the debugger.',
           '']
    for title,a in SITES.items():
        if title in ['front_end_caller','initial_menu_state','selector_start','accept_dispatch_start',
                     'arcade_entry','arrange_entry','gallery_entry','options_entry','exit_entry','top_level_return']:
            lines.append(f'0x{a:08X}  {title}')
    lines.extend(['','Expected upon pressing accept on the five mode-select choices:',
                  'Arcade -> 0x001CA800 / state 2',
                  'Arrange -> 0x001CA824 / state 9',
                  'Gallery -> 0x001CA848 / result 2',
                  'Option -> 0x001CA860 / state 13',
                  'Exit -> 0x001CA7E4 / result 1',
                  '', 'Follow-up (when convenient): confirm which path the actual hardware/PCSX2 takes.',
                  'This file describes a static analysis prediction, not a completed runtime trace.'])
    return '\n'.join(lines)+'\n'


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source',type=Path,help='Original Japanese retail ISO or extracted ELF')
    ap.add_argument('--out',type=Path,help='JSON output path (no game assets)')
    ap.add_argument('--breakpoints',type=Path,help='Write a PCSX2 debugger checklist')
    ap.add_argument('--sprites',type=Path,help='Export two ORIGINAL menu texture PNGs from your own ISO (requires Pillow)')
    args=ap.parse_args()
    elf, iso_files, disc_file = retail.load_input(args.source)
    info=retail.elf_summary(elf)
    assert info['machine']==8,'Not a MIPS ELF'
    if info['sha256']!=ORIGINAL_SHA256:
        raise SystemExit('ABORT: Input ELF does not match unmodified SLPM_663.01 revision\n  got '+info['sha256'])
    mapping=make_map(elf,info)
    result={'source':args.source.name, 'elf_sha256':info['sha256'],
            'iso_disc_boot_extent':disc_file, 'mode_selector':mapping,
            'model':'Static verification only; runtime not yet tested',
            'safety':['No data in source was modified',
                      'A sixth item may fill two zero pointer slots; it still requires new graphics descriptors and a guarded dispatch hook',
                      'Four loop-bound changes alone are NOT a functioning menu patch',
                      'Full Black Label graphics and code do not exist in this retail ISO']}
    if iso_files:
        result['resource_index']=asset_info(args.source,iso_files)
        if args.sprites:
            result['exported_sprite_paths']=export_sprites(args.source,iso_files,args.sprites,result['resource_index'])
    elif args.sprites:
        ap.error('--sprites requires ISO input')
    print('Verified retail ELF',info['sha256'][:16])
    print('Top-level five-entry selector: 0x001CA42C')
    for row in mapping['state_dispatch']:
        print(f"  {row['index']} {row['label']:<14} {row['address']} -> {row['result']}")
    print('Four distinct immediate <5 checks verified at:', ', '.join(f'0x{a:08X}' for a in LIMITS))
    print('Position seed values:',', '.join(hex(v) for v in mapping['anchor_values']))
    print('Menu texture atlas:',', '.join(str(x) for x in PDM_IDS))
    if args.out:
        args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        print('Wrote JSON:',args.out)
    if args.breakpoints:
        args.breakpoints.write_text(breakpoint_text(),encoding='utf-8')
        print('Wrote breakpoints:',args.breakpoints)
    if args.sprites:
        print('Exported original texture pages:',args.sprites)

if __name__=='__main__': main()
