#!/usr/bin/env python3
"""Read-only Ibara (Japan) SLPM-66301 ISO9660 and IBARAR resource audit.

Python 3 standard library only. Never writes to or patches the input ISO.

  python ibara_complete_phase2_audit.py "Ibara (Japan).iso" \
      --json phase2.json --csv resources.csv --scan-gap

The report/catalog contain metadata, NOT extracted copyrighted game assets.
Supports plain 2048-byte-sector ISOs only; extract .7z to .iso first.
"""
from __future__ import annotations
import argparse,collections,csv,hashlib,json,struct,zlib
from pathlib import Path

SECTOR=2048
EXPECTED={
 'SLPM_663.01':(2329648,0xF9085060),
 'IBARAR.PDM':(241377288,0xF0A452FE),
 'IBARAR.TBL':(18100,0xA286422C),
 'ALLIMAGE.DAT':(1555136,0xC09F7BED),
}
VISUAL_OFFSETS={
 'mode_top_left':0x2D73000,'mode_bottom_left':0x2D83800,
 'mode_top_center':0x2D94000,'mode_bottom_center':0x2DA4800,
 'mode_right_both_halves':0x2DB5000,
 'title_left':0x45D4000,'title_right':0x4636800,
 'title_v_bottom_left':0x4699000,'title_v_bottom_right':0x46FB800,
 'frontend_menu_sprite_A':0x2D20800,'frontend_menu_sprite_B':0x2D31000,
}

def u16(b,p):return struct.unpack_from('<H',b,p)[0]
def u32(b,p):return struct.unpack_from('<I',b,p)[0]
def iso_record(b,p):
 n=b[p]
 if n==0 or p+n>len(b):return None
 r=b[p:p+n]
 if len(r)<34:raise ValueError('Invalid ISO9660 directory record at '+str(p))
 l=r[32]
 name=r[33:33+l].decode('ascii','replace')
 return {'length':n,'name':name,'lba':u32(r,2),'bytes':u32(r,10),'flags':r[25]}

def iso_files(f):
 f.seek(16*SECTOR); pvd=f.read(SECTOR)
 if pvd[:7]!=b'\x01CD001\x01':raise ValueError('Not a plain ISO9660 image')
 root=iso_record(pvd,156)
 if root is None:raise ValueError('Root directory missing')
 todo=[('',root)]; files={};seen=set()
 while todo:
  parent,folder=todo.pop()
  if folder['lba'] in seen:continue
  seen.add(folder['lba'])
  f.seek(folder['lba']*SECTOR); block=f.read(folder['bytes'])
  at=0
  while at<len(block):
   if block[at]==0:
    at=(at//SECTOR+1)*SECTOR;continue
   rec=iso_record(block,at)
   if rec is None:raise ValueError('Bad ISO9660 directory at '+str(at))
   at+=rec['length']
   if rec['name'] in ('\x00','\x01'):continue
   stem=rec['name'].split(';')[0]
   path=parent+'/'+stem
   rec['path']=path
   if rec['flags']&2:todo.append((path,rec))
   else:files[path]=rec
 return pvd,root,files

def crc_region(f,off,sz):
 f.seek(off);c=0
 while sz:
  b=f.read(min(4*1024*1024,sz))
  if not b:raise ValueError('Unexpected end of ISO')
  c=zlib.crc32(b,c);sz-=len(b)
 return c

def zero_region(f,start,length):
 f.seek(start);left=length;count=0
 while left:
  b=f.read(min(4*1024*1024,left))
  if not b:raise ValueError('Unexpected end while scanning gap')
  count+=len(b)-b.count(0);left-=len(b)
 return count

def audit(iso,scan_gap=False):
 with iso.open('rb') as f:
  pvd,root,files=iso_files(f)
  stats={'input':iso.name,'iso_bytes':iso.stat().st_size,
         'volume_id':pvd[40:72].decode('ascii','replace').strip(),
         'volume_sectors':u32(pvd,80),
         'files':{},'resource_count':None}
  names={x['name'].split(';')[0]:x for x in files.values()}
  for name,(sz,expected_crc) in EXPECTED.items():
   rec=names.get(name)
   if rec is None:raise ValueError('Missing '+name)
   crc=crc_region(f,rec['lba']*SECTOR,rec['bytes'])
   stats['files'][name]={'lba':rec['lba'],'bytes':rec['bytes'],
       'crc32':f'{crc:08X}','matches_reference_crc':crc==expected_crc,
       'matches_reference_size':rec['bytes']==sz}
  f.seek(root['lba']*SECTOR);d=f.read(SECTOR)
  root_entries=[];at=0
  while at<root['bytes'] and d[at]:
   r=iso_record(d,at);root_entries.append(r['name']);at+=r['length']
  stats['root_directory']={'lba':root['lba'],'logical_bytes':root['bytes'],
          'occupied_bytes':at,'physical_sector_slack':SECTOR-at,
          'slack_all_zero':d[at:]==b'\0'*(SECTOR-at),
          'entries':root_entries,
          'note':'Adding a file requires adjusting ISO9660 root-size and entry metadata.'}
  dummy=names.get('DAMMY1G.DAT')
  if dummy:
   end_dummy=dummy['lba']+(dummy['bytes']+SECTOR-1)//SECTOR
   later=min((x['lba'] for x in files.values() if x['lba']>=end_dummy),default=None)
   if later:
    start=end_dummy*SECTOR;count=(later-end_dummy)*SECTOR
    gap={'start_lba':end_dummy,'end_lba_exclusive':later,'bytes':count,
         'scan_performed':bool(scan_gap)}
    if scan_gap:
     gap['nonzero_bytes']=zero_region(f,start,count)
     gap['fully_zero']=gap['nonzero_bytes']==0
    stats['unallocated_gap_after_dummy']=gap
  t=names['IBARAR.TBL'];pd=names['IBARAR.PDM']
  f.seek(t['lba']*SECTOR);b=f.read(t['bytes'])
  if b[:4]!=b'TBL\x04':raise ValueError('Unexpected resource table signature')
  packed=u32(b,8); n=packed>>16; record_start=packed&0xFFFF
  if n!=1130 or record_start!=0x11BC:raise ValueError('Unexpected resource-table layout')
  catalog=[];magics=collections.Counter();sizes=collections.Counter()
  for i in range(n):
   rpos=u32(b,20+i*4)
   if rpos!=record_start+i*8:raise ValueError(f'Index {i}: bad record pointer')
   offptr=u32(b,rpos);length=u32(b,rpos+4)
   if offptr!=0x350C+i*4:raise ValueError(f'Index {i}: bad data-offset pointer')
   off=u32(b,offptr)
   if off%SECTOR:raise ValueError(f'Index {i}: unaligned data')
   if i<n-1:
    nextpos=u32(b,0x350C+(i+1)*4)
    if nextpos-off != (length+SECTOR-1)//SECTOR*SECTOR:
     raise ValueError(f'Index {i}: inconsistent length/alignment')
   if off+length>pd['bytes']:raise ValueError(f'Index {i}: past PDM end')
   f.seek(pd['lba']*SECTOR+off);head=f.read(160)
   magic=head[:4].decode('ascii','replace')
   if magic not in ('TIM2','BG00','SE00'):raise ValueError(f'Index {i}: unrecognized magic {magic!r}')
   rec={'index':i,'pdm_offset':off,'pdm_size':length,'disc_byte_offset':pd['lba']*SECTOR+off,
        'magic':magic,'width':'','height':'','image_type':'','clut_type':''}
   if magic=='TIM2':
    picbase=128 if head[5] else 16
    if picbase+24>len(head):raise ValueError('TIM2 short header')
    h=head[picbase:picbase+24]
    rec.update(width=u16(h,20),height=u16(h,22),image_type=h[19],clut_type=h[18])
    sizes[(rec['width'],rec['height'],rec['image_type'])]+=1
   catalog.append(rec);magics[magic]+=1
  stats['resource_count']=n
  stats['table_format']={'header_bytes':20,'index_pointers_start':20,
      'record_area_start':record_start,'offset_table_start':0x350C,
      'offsets_are_relative_to':'IBARAR.PDM','sector_alignment':SECTOR,
      'trailing_bytes_after_last_resource':pd['bytes']-(catalog[-1]['pdm_offset']+catalog[-1]['pdm_size'])}
  stats['resource_types']=dict(magics)
  stats['tim2_dimensions_and_formats']=[{'width':w,'height':h,'image_type':t,'count':n}
     for (w,h,t),n in sizes.most_common()]
  oidx={r['pdm_offset']:r['index'] for r in catalog}
  stats['frontend_art_indexes']={k:oidx.get(off) for k,off in VISUAL_OFFSETS.items()}
  stats['notes']=['This is metadata only, no game assets or executables are output.',
       'Mode artwork positions are corroborated by ibara360 tools/ps2extract/mkrecipe.py.',
       'A separate Black Label binary has NOT been ported to PS2.',
       'Physical ISO space is not the same as proved working EE RAM/GS VRAM.',
       'Do not edit the source ISO; prove a read-only metadata baseline first.']
  return stats,catalog

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('iso',type=Path)
 ap.add_argument('--json',type=Path)
 ap.add_argument('--csv',type=Path)
 ap.add_argument('--scan-gap',action='store_true',help='Read the entire unallocated gap to verify that all bytes are zero')
 a=ap.parse_args()
 if not a.iso.is_file():ap.error('ISO not found (extract the 7z first)')
 stats,rows=audit(a.iso,a.scan_gap)
 print('ISO:',stats['iso_bytes'],'bytes, volume:',stats['volume_id'])
 for k,v in stats['files'].items():
  print(k, 'LBA',v['lba'],'size',v['bytes'],'CRC32',v['crc32'], 'matches reference:',v['matches_reference_crc'])
 print('PDM resource types:',stats['resource_types'])
 print('Frontend art index map:',stats['frontend_art_indexes'])
 print('Root directory:',stats['root_directory']['logical_bytes'],'bytes; zero trailing slack:',stats['root_directory']['physical_sector_slack'])
 print('After-dummy gap:',stats.get('unallocated_gap_after_dummy'))
 if a.json:
  a.json.write_text(json.dumps(stats,indent=2,ensure_ascii=False)+'\n',encoding='utf8');print('Metadata JSON:',a.json)
 if a.csv:
  with a.csv.open('w',newline='',encoding='utf8') as fp:
   w=csv.DictWriter(fp,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
  print('Metadata CSV:',a.csv)

if __name__=='__main__':main()
