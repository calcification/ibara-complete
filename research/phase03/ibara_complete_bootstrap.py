#!/usr/bin/env python3
"""Ibara Complete Phase 3: non-destructive ISO9660 + PS2 ELF boot-probe builder.

Requires an UNMODIFIED Ibara (Japan) SLPM-66301 2048-byte/sector ISO.
Produces a SEPARATE test ISO; never writes to, modifies, or distributes input.

Modes:
  inject  Add KURO.ELF;1 but retain original SLPM_663.01 as the disc boot file.
  probe   Add KURO.ELF;1 and redirect SYSTEM.CNF to boot it; original files remain
          byte-identical in their original locations, but the retail game does
          NOT boot in this mode. This is an isolated loader test, not a menu mod.

Probe ELF: minimal original MIPS III/R5900-compatible assembly that sets GS
PMODE.SLBG and BGCOLOR to magenta, then loops. If the BIOS has not initialized
video output sufficiently, the screen can remain blank despite execution.
It does NOT implement Black Label and does NOT change the normal retail menu.

Example:
  python ibara_complete_bootstrap.py "Ibara (Japan).iso" --mode probe \\
      --output "Ibara-Complete-Probe.iso"
  python ibara_complete_bootstrap.py "Ibara (Japan).iso" --mode inject \\
      --output "Ibara-Complete-Injected.iso"

Requires Python 3.9+ standard library only. Works on Windows, macOS, Linux.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import zlib

SECTOR = 2048
EXPECTED_SHA256 = '6e58b52aa5c03d45e413e8473be52a39205095e34a1bd58dae6bd852eb4fb1db'
EXPECTED_ISO_LEN = 3932848128
EXPECTED_ELF_SHA256 = '263d3079dee66af82815219351553075340a4d9f42aceaa7bb8ef2bfb812ffac'
ORIGINAL_ROOT_LBA = 261
ORIGINAL_ROOT_LEN = 570
NEW_FILE_LBA = 500286
NEW_CNF_LBA = NEW_FILE_LBA + 1
NEXT_ORIGINAL_FILE_LBA = 1800286
PROBE_FILENAME = b'KURO.ELF;1'
EXPECTED_CRC = {
    'SLPM_663.01;1': (1919173, 2329648, 0xF9085060),
    'IBARAR.PDM;1': (1801312, 241377288, 0xF0A452FE),
    'IBARAR.TBL;1': (1920311, 18100, 0xA286422C),
    'ALLIMAGE.DAT;1': (1800552, 1555136, 0xC09F7BED),
}


def pair32(value: int) -> bytes:
    return struct.pack('<I', value) + struct.pack('>I', value)


def pair16(value: int) -> bytes:
    return struct.pack('<H', value) + struct.pack('>H', value)


def uint32(buf: bytes, off: int) -> int:
    return struct.unpack_from('<I', buf, off)[0]


def read_at(fh, offset: int, length: int) -> bytes:
    fh.seek(offset)
    data = fh.read(length)
    if len(data) != length:
        raise ValueError(f'Short read at 0x{offset:X}')
    return data


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def parse_record(buf: bytes, off: int) -> dict:
    nbytes = buf[off]
    if nbytes < 34 or off + nbytes > len(buf):
        raise ValueError(f'Bad ISO9660 directory record at {off}')
    namelen = buf[off + 32]
    name = buf[off + 33:off + 33 + namelen]
    if (uint32(buf, off+2) != int.from_bytes(buf[off+6:off+10], 'big') or
        uint32(buf, off+10) != int.from_bytes(buf[off+14:off+18], 'big')):
        raise ValueError(f'ISO9660 endian mismatch for record {name!r}')
    return dict(offset=off, record_bytes=nbytes, name=name,
                lba=uint32(buf, off+2), size=uint32(buf, off+10),
                flags=buf[off+25])


def read_root(fh):
    pvd = read_at(fh, 16 * SECTOR, SECTOR)
    if pvd[:7] != b'\x01CD001\x01':
        raise ValueError('Primary Volume Descriptor not found')
    if uint32(pvd, 80) * SECTOR != EXPECTED_ISO_LEN:
        raise ValueError('Unexpected volume sector count')
    pr = parse_record(pvd, 156)
    if pr['lba'] != ORIGINAL_ROOT_LBA or pr['size'] != ORIGINAL_ROOT_LEN:
        raise ValueError('Unexpected PVD root directory location/length')
    root = read_at(fh, ORIGINAL_ROOT_LBA * SECTOR, SECTOR)
    records=[]; off=0
    while off < ORIGINAL_ROOT_LEN:
        rec=parse_record(root, off)
        records.append(rec)
        off += rec['record_bytes']
    if off != ORIGINAL_ROOT_LEN or root[ORIGINAL_ROOT_LEN:] != b'\0'*(SECTOR-ORIGINAL_ROOT_LEN):
        raise ValueError('Root directory records or trailing space unexpected')
    for r in records[:2]:
        if r['lba'] != ORIGINAL_ROOT_LBA or r['size'] != ORIGINAL_ROOT_LEN:
            raise ValueError('Root self/parent size mismatch')
    return pvd, root, records


def build_probe_elf():
    # MIPS III EE instructions assembled independently with LLVM's MIPS backend.
    # lui t0,0x1200          ; GS MMIO @ 0x12000000
    # addiu t1,zero,0x20   ; PMODE SLBG = 1, screen from GS background
    # sd t1,0(t0)          ; PMODE
    # lui t1,0x00ff
    # ori t1,t1,0x00ff     ; BGCOLOR magenta, channels R=FF,G=00,B=FF
    # sd t1,0xe0(t0)       ; BGCOLOR
    # loop: b loop
    #       nop
    instructions = [
        0x3c081200, 0x24090020, 0xfd090000,
        0x3c0900ff, 0x352900ff, 0xfd0900e0,
        0x1000ffff, 0x00000000,
    ]
    code = struct.pack('<8I', *instructions)
    hdr = bytearray(0x80)
    hdr[:16] = b'\x7fELF\x01\x01\x01' + b'\0'*9
    struct.pack_into('<HHIIIIIHHHHHH', hdr, 16,
                     2, 8, 1, 0x00100000, 52, 0,
                     0x20924000, 52, 32, 1, 0, 0, 0)
    struct.pack_into('<8I', hdr, 52,
                     1, 0x80, 0x00100000, 0x00100000,
                     len(code), len(code), 7, 0x80)
    return bytes(hdr)+code


def make_file_record(name: bytes, lba: int, size: int):
    n=33 + len(name) + (len(name)%2 == 0)
    rec=bytearray(n)
    rec[0] = n
    rec[2:10] = pair32(lba)
    rec[10:18] = pair32(size)
    rec[18:25] = bytes([126,11,19,12,0,0,0])
    rec[25] = 0    # file, not directory
    rec[26] = 0    # not interleaved
    rec[27] = 0
    rec[28:32] = pair16(1)
    rec[32] = len(name)
    rec[33:33+len(name)] = name
    return bytes(rec)


def crc_region(fh, lba, length):
    fh.seek(lba*SECTOR)
    remain=length; crc=0
    while remain:
        data=fh.read(min(remain, 2*1024*1024))
        if not data: raise ValueError('Missing bytes in recorded file extent')
        crc=zlib.crc32(data,crc)
        remain-=len(data)
    return crc & 0xffffffff


def check_source(src: Path):
    if not src.is_file() or src.stat().st_size != EXPECTED_ISO_LEN:
        raise ValueError('Source ISO size does not match the original retail image')
    iso_hash=digest_file(src)
    if iso_hash != EXPECTED_SHA256:
        raise ValueError(f'Original ISO SHA-256 mismatch: {iso_hash}')
    with src.open('rb') as fh:
        pvd,root,records=read_root(fh)
        names={rec['name'].decode('ascii',errors='replace'):rec for rec in records}
        if len(records)!=10 or PROBE_FILENAME.decode() in names:
            raise ValueError('Original root directory is not the expected retail revision')
        for filename,(lba,size,expected_crc) in EXPECTED_CRC.items():
            rec=names.get(filename)
            if rec is None or (rec['lba'],rec['size'])!=(lba,size):
                raise ValueError(f'Retail entry differs: {filename}')
            if crc_region(fh,lba,size)!=expected_crc:
                raise ValueError(f'Retail file CRC differs: {filename}')
        cnf=names['SYSTEM.CNF;1']
        orig_cnf=read_at(fh,cnf['lba']*SECTOR,cnf['size'])
        if b'BOOT2 = cdrom0:\\SLPM_663.01;1\r\n' not in orig_cnf:
            raise ValueError('Unknown original SYSTEM.CNF boot path')
        for lba in (NEW_FILE_LBA,NEW_CNF_LBA):
            if read_at(fh,lba*SECTOR,SECTOR)!=b'\0'*SECTOR:
                raise ValueError('Injection sectors are not all zero')
        if NEW_FILE_LBA+2 >= NEXT_ORIGINAL_FILE_LBA:
            raise ValueError('No room for injected file')
    return pvd,root,records,orig_cnf,iso_hash


def inject(src: Path, dst: Path, mode: str, *, check_only: bool = False):
    pvd,root,records,orig_cnf,iso_hash = check_source(src)
    payload=build_probe_elf()
    if not payload.startswith(b'\x7fELF') or len(payload)>SECTOR:
        raise ValueError('Probe ELF is invalid or too large')
    new_cnf=orig_cnf.replace(b'SLPM_663.01;1', b'KURO.ELF;1')
    if len(new_cnf)==len(orig_cnf):
        raise ValueError('Expected changed SYSTEM.CNF length')
    new_record=make_file_record(PROBE_FILENAME,NEW_FILE_LBA,len(payload))
    root_length=ORIGINAL_ROOT_LEN+len(new_record)
    if root_length>SECTOR:
        raise ValueError('Root directory needs a second sector')
    new_root=bytearray(root)
    new_root[ORIGINAL_ROOT_LEN:root_length]=new_record
    for r in records[:2]:
        off=r['offset']
        new_root[off+10:off+18]=pair32(root_length)
    if mode=='probe':
        system=next(r for r in records if r['name']==b'SYSTEM.CNF;1')
        new_root[system['offset']+2:system['offset']+10]=pair32(NEW_CNF_LBA)
        new_root[system['offset']+10:system['offset']+18]=pair32(len(new_cnf))
    new_pvd=bytearray(pvd)
    new_pvd[156+10:156+18]=pair32(root_length)
    if check_only:
        return {"mode":mode,"input_sha256":iso_hash,"probe_elf_bytes":len(payload),"root_bytes_before":ORIGINAL_ROOT_LEN,"root_bytes_after":root_length,"probe_elf_sha256":hashlib.sha256(payload).hexdigest(),"new_system_cnf_bytes":len(new_cnf),"dry_run":True}
    if dst.exists():
        raise ValueError('Output exists; choose a new path. Refusing to overwrite.')
    if dst.resolve()==src.resolve():
        raise ValueError('Output path must differ from original ISO')
    try:
        # Full local copy, no in-place alteration. May require ~3.7 GB free space.
        with src.open('rb') as original, dst.open('xb') as out:
            shutil.copyfileobj(original,out,8*1024*1024)
            out.flush()
        with dst.open('r+b') as out:
            out.seek(16*SECTOR)
            out.write(new_pvd)
            out.seek(ORIGINAL_ROOT_LBA*SECTOR)
            out.write(new_root)
            out.seek(NEW_FILE_LBA*SECTOR)
            out.write(payload)
            if mode=='probe':
                out.seek(NEW_CNF_LBA*SECTOR)
                out.write(new_cnf)
            out.flush()
        with dst.open('rb') as f:
            # Independent round-trip checks of root, original files and injected bytes.
            pp=read_at(f,16*SECTOR,SECTOR)
            rr=read_at(f,ORIGINAL_ROOT_LBA*SECTOR,SECTOR)
            if pp[156+10:156+18]!=pair32(root_length):
                raise ValueError('Post-write PVD root size mismatch')
            entries=[];i=0
            while i<root_length:
                r=parse_record(rr,i);entries.append(r);i+=r['record_bytes']
            if i != root_length or len(entries)!=11:
                raise ValueError('Post-write root directory record count/length mismatch')
            got = next((r for r in entries if r['name']==PROBE_FILENAME),None)
            if got is None or (got['lba'],got['size'])!=(NEW_FILE_LBA,len(payload)):
                raise ValueError('KURO.ELF not registered correctly')
            if read_at(f,NEW_FILE_LBA*SECTOR,len(payload)) != payload:
                raise ValueError('KURO.ELF contents corrupted')
            for r in entries[:2]:
                if r['size'] != root_length:raise ValueError('Root self record not updated')
            bootrec=next(r for r in entries if r['name']==b'SYSTEM.CNF;1')
            boot_data=read_at(f,bootrec['lba']*SECTOR,bootrec['size'])
            expected_cnf=new_cnf if mode=='probe' else orig_cnf
            if boot_data!=expected_cnf:raise ValueError('SYSTEM.CNF incorrect')
            for filename,(lba,size,crc) in EXPECTED_CRC.items():
                r=next((r for r in entries if r['name']==filename.encode('ascii')),None)
                if r is None or (r['lba'],r['size'])!=(lba,size):
                    raise ValueError(f'Original file extent changed: {filename}')
                if crc_region(f,lba,size)!=crc:
                    raise ValueError(f'Original file bytes changed: {filename}')
        if digest_file(src)!=iso_hash:
            raise ValueError('Original ISO hash changed unexpectedly')
    except Exception:
        dst.unlink(missing_ok=True)
        raise
    return {"mode":mode,"source_iso_sha256":iso_hash,"iso_bytes":EXPECTED_ISO_LEN,
            "output_path":str(dst),"new_file":"KURO.ELF;1","new_file_lba":NEW_FILE_LBA,
            "probe_elf_bytes":len(payload),"probe_elf_sha256":hashlib.sha256(payload).hexdigest(),
            "new_system_cnf_lba":NEW_CNF_LBA if mode=='probe' else None,
            "boot":"KURO.ELF;1 (test only)" if mode=='probe' else "SLPM_663.01;1 (retail)",
            "original_game_files_crc_unchanged":True,
            "original_iso_sha256_unchanged":True,"root_directory_bytes":root_length,
            "runtime_tested":False}


def main():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('iso',type=Path,help='Exact unmodified Japanese Ibara SLPM-66301 ISO')
    p.add_argument('--mode',choices=['inject','probe'],required=True)
    p.add_argument('--output',type=Path,help='Path for a new separate 3.66 GiB test ISO')
    p.add_argument('--dry-run',action='store_true',help='Verify source and report proposed changes, without writing')
    p.add_argument('--report',type=Path,help='Optional JSON report location')
    args=p.parse_args()
    if not args.dry_run and args.output is None:p.error('--output is required without --dry-run')
    try:
        result=inject(args.iso,args.output,args.mode,check_only=args.dry_run)
    except (OSError,ValueError) as exc:
        p.error(str(exc))
    print(json.dumps(result,indent=2))
    if args.report:
        args.report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')


if __name__ == '__main__':
    main()
