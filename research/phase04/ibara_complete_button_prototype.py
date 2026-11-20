#!/usr/bin/env python3
"""Ibara Complete: asset-only BLACK LABEL button prototype (not a working game mode).

This makes a NEW button by processing resource #946 from YOUR OWN Ibara
SLPM-66301 retail ISO. It writes only texture indices in a pre-existing
112x48 transparent region. The resource table, file lengths, and executable
stay unchanged. No copyrighted resource data is included with the script.

Usage:
  python ibara_complete_button_prototype.py "Ibara (Japan).iso" --preview button_preview.png
  python ibara_complete_button_prototype.py "Ibara (Japan).iso" --apply-to "Ibara Complete ASSET ONLY.iso" --preview button_preview.png

Requires pillow and numpy: pip install pillow numpy
Optional OpenCV for smoother plate inpainting: pip install opencv-python

The applied ISO is an experimental asset test only: the added button remains
INVISIBLE in the retail game until the top-level renderer is extended.
"""
import argparse, json, shutil, struct
from pathlib import Path
import ibara_complete_audit as retail
import ibara_complete_menu_map as menus

ID=946
TEX_RECT=(112,96,224,144)
SOURCE_RECT=(0,96,112,144)
ORIGINAL_ELF_SHA=menus.ORIGINAL_SHA256
EXPECTED_PDM_CRC=0xF0A452FE


def meta(fh, files):
    tbl=next(e for e in files if e['name'].split(';')[0].upper()=='IBARAR.TBL')
    pdm=next(e for e in files if e['name'].split(';')[0].upper()=='IBARAR.PDM')
    fh.seek(tbl['lba']*2048);b=fh.read(tbl['bytes'])
    if b[:4]!=b'TBL\x04' or len(b)!=18100:raise ValueError('Wrong TBL')
    off=struct.unpack_from('<I',b,0x350C+ID*4)[0]
    size=struct.unpack_from('<I',b,0x11BC+ID*8+4)[0]
    if off!=0x2D31000 or size!=66624:raise ValueError('Unexpected texture layout')
    base=pdm['lba']*2048+off
    fh.seek(base);h=fh.read(16)
    if h[:4]!=b'TIM2':raise ValueError('Wrong format')
    delta=128 if h[5] else 16
    fh.seek(base+delta);p=fh.read(24)
    total,clut_len,image_len,head_len,colors,_,mip,clut_typ,img_typ,w,hgt=struct.unpack_from('<IIIHHBBBBHH',p)
    if (image_len,clut_len,img_typ,clut_typ&0x1f,w,hgt)!=(65536,1024,5,3,256,256):
        raise ValueError('Unexpected indexed TIM2 image format')
    return {'file_start':base, 'image_byte_start':base+delta+head_len,
            'clut_start':base+delta+head_len+image_len,'header_type':clut_typ,
            'image_len':image_len,'palette_len':clut_len,'width':w,'height':hgt}


def palette_from_bytes(clut,ctype):
    import numpy as np
    cols=np.frombuffer(clut,dtype=np.uint8).reshape(-1,4).copy()
    # PS2 TIM2 palette alpha is 0..128 (255 means fully opaque after scaling).
    cols[:,3]=np.minimum(255,(cols[:,3].astype(np.uint16)*255)//128).astype(np.uint8)
    if not (ctype&0x80):
        for base in range(0,256,32):
            cols[base+8:base+16],cols[base+16:base+24] = cols[base+16:base+24].copy(),cols[base+8:base+16].copy()
    return cols


def original_image(indices,colors):
    from PIL import Image
    import numpy as np
    rgba=colors[np.frombuffer(indices,dtype=np.uint8).reshape(256,256)]
    return Image.fromarray(rgba,'RGBA')


def generate_button(image):
    from PIL import Image,ImageDraw,ImageFont
    import numpy as np
    source=image.crop(SOURCE_RECT).convert('RGBA')
    r=np.array(source)
    try:
        import cv2
        mask=np.zeros((48,112),dtype=np.uint8)
        mask[12:37,17:83]=255
        r[:,:,:3]=cv2.inpaint(r[:,:,:3],mask,4,cv2.INPAINT_TELEA)
        method='opencv inpaint'
    except ImportError:
        # Dependency-free fallback: use textured metal sampled from a nearby
        # unlettered portion of the button. Leave ornamental edges intact.
        for y in range(12,37):
            reference=r[y,84:94,:3].copy()
            for x in range(17,83):
                k=(x-17)%len(reference)
                r[y,x,:3]=reference[k]
        method='Pillow fallback metal fill'
    plate=Image.fromarray(r,'RGBA')
    d=ImageDraw.Draw(plate)
    fonts=['DejaVuSerifCondensed-Bold.ttf','LiberationSerif-Bold.ttf','DejaVuSerif-Bold.ttf']
    font=None
    for sz in range(15,9,-1):
        for fname in fonts:
            try:
                f=ImageFont.truetype(fname,sz)
            except OSError: continue
            b=d.textbbox((0,0),'BLACK LABEL',font=f,stroke_width=1)
            if b[2]-b[0] <= 94 and b[3]-b[1]<=23:
                font=f;break
        if font:break
    if font is None:
        font=ImageFont.load_default()
    b=d.textbbox((0,0),'BLACK LABEL',font=font,stroke_width=1)
    tw=b[2]-b[0];th=b[3]-b[1]
    x=(112-tw)//2-b[0];y=24-th//2-b[1]
    d.text((x+1,y+2),'BLACK LABEL',font=font,fill=(8,21,43,255),stroke_width=1,stroke_fill=(9,21,42,255))
    d.text((x,y),'BLACK LABEL',font=font,fill=(248,246,244,255),stroke_width=1,stroke_fill=(15,68,170,255))
    return plate,method


def quantize(image,palette):
    import numpy as np
    p=np.asarray(image.convert('RGBA'),dtype=np.int16).reshape(-1,4)
    pal=palette.astype(np.int16)
    # Compare each pixel with all 256 palette colors, weighting alpha heavily.
    a=(p[:,None,:]-pal[None,:,:]).astype(np.int32)
    cost=(a[:,:,:3]*a[:,:,:3]).sum(axis=2) + 5*a[:,:,3]*a[:,:,3]
    return cost.argmin(axis=1).astype(np.uint8).reshape(image.height,image.width)


def apply_indices(raw, new_tile):
    r=bytearray(raw)
    touched=[]
    for j in range(48):
        start=(96+j)*256+112
        old=bytes(r[start:start+112]);new=bytes(new_tile[j,:])
        if old != new:
            r[start:start+112]=new
            touched.append((start,old,new))
    return bytes(r),touched


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('iso',type=Path)
    ap.add_argument('--preview',type=Path,help='Output preview PNG of the modified resource 946')
    ap.add_argument('--report',type=Path,help='Output asset modification metadata JSON')
    ap.add_argument('--apply-to',type=Path,help='Write modified-copy ISO (never overwrites original)')
    args=ap.parse_args()
    if not args.preview and not args.report and not args.apply_to:
        ap.error('Specify --preview, --report and/or --apply-to')
    if args.apply_to and args.iso.resolve()==args.apply_to.resolve():ap.error('Refusing to overwrite original ISO')
    _,files,disc=retail.load_input(args.iso)
    if not files or not disc:ap.error('Expected original ISO, not ELF')
    # Avoid re-reading huge ISO or hashing resource archive: exact ELF SHA
    # + expected image/TBL structure is the validation for this prototype.
    with args.iso.open('rb') as f:
        f.seek(disc['lba']*2048);elf=f.read(disc['bytes'])
        import hashlib
        if hashlib.sha256(elf).hexdigest()!=ORIGINAL_ELF_SHA:
            raise ValueError('Wrong retail revision')
        info=meta(f,files)
        f.seek(info['image_byte_start']);raw=f.read(info['image_len'])
        f.seek(info['clut_start']);pal_raw=f.read(info['palette_len'])
    palette=palette_from_bytes(pal_raw,info['header_type'])
    original=original_image(raw,palette)
    empty=original.crop(TEX_RECT).getchannel('A')
    if empty.getextrema()!=(0,0):raise ValueError('Refusing to overwrite occupied pixels in target slot')
    plate,method=generate_button(original)
    idx=quantize(plate,palette)
    modified,touched=apply_indices(raw,idx)
    import numpy as np
    assert len(raw)==len(modified)==65536
    diff=np.frombuffer(raw,dtype=np.uint8)!=np.frombuffer(modified,dtype=np.uint8)
    mask=np.zeros(65536,dtype=bool)
    for y in range(96,144):mask[y*256+112:y*256+224]=True
    if np.any(diff & ~mask):raise AssertionError('Bytes outside reserved pixel slot were altered')
    changed=int(diff.sum());print('Changed texture index bytes:',changed)
    preview=original_image(modified,palette)
    if args.preview:
        args.preview.parent.mkdir(parents=True,exist_ok=True)
        preview.save(args.preview)
        print('Preview:',args.preview)
    if args.apply_to:
        args.apply_to.parent.mkdir(parents=True,exist_ok=True)
        print('Copying source ISO (approx. 3.7 GB) ...')
        shutil.copyfile(args.iso,args.apply_to)
        with args.apply_to.open('r+b') as outf:
            for offset,_,new in touched:
                outf.seek(info['image_byte_start']+offset)
                outf.write(new)
        # Re-read exactly the 64KB modified texture, verify equality.
        with args.apply_to.open('rb') as outf:
            outf.seek(info['image_byte_start'])
            if outf.read(65536)!=modified:raise AssertionError('Write verification failed')
        print('Asset-only ISO copy:',args.apply_to)
    report={'source':args.iso.name,'elf_sha256':ORIGINAL_ELF_SHA,
            'resource_id':946,'resource_pdm_offset':'0x2D31000',
            'texture_dimensions':[256,256], 'new_button_rect':list(TEX_RECT),
            'existing_button_source_rect':list(SOURCE_RECT),
            'index_bytes_changed':changed,'total_pixels_outside_rect_modified':0,
            'original_resource_size_unchanged':True,
            'source_iso_modified':False,'inpaint_method':method,
            'runtime_status':'ASSET ONLY: not drawn by original menu; requires future renderer and dispatch changes',
            'copy_output':str(args.apply_to) if args.apply_to else None}
    if args.report:
        args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
        print('Report:',args.report)
    else:print(json.dumps(report,indent=2))

if __name__=='__main__':main()
