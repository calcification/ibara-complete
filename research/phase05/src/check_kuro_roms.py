#!/usr/bin/env python3
"""Check whether a user-provided arcade ZIP contains the four known Ibara Kuro ROM chips.

Reads ZIP metadata, not ROM payload; --verify-payload recomputes CRC32 over bytes.
Does not create, download, redistribute, or extract any copyrighted data.
Reference: ibara360 host/xsdk/ibara360/source/romload.c.
"""
import argparse
import json
from pathlib import Path
from zipfile import ZipFile
import zlib

ROM_CHIPS = {
    'U4':  (0x200000, 0xEE1F1F77),
    'U2':  (0x8400000, 0x5E46BE44),
    'U23': (0x400000, 0xA436BB22),
    'U24': (0x400000, 0xD11AB6B6),
}

def inspect(path, verify_payload=False):
    output=[]
    with ZipFile(path) as z:
        members=[info for info in z.infolist() if not info.is_dir()]
        for role,(size,crc) in ROM_CHIPS.items():
            candidates=[info for info in members if info.file_size==size and info.CRC==crc]
            status='missing' if not candidates else 'metadata_match'
            if verify_payload and candidates:
                status='verified'
                with z.open(candidates[0]) as f:
                    val=0
                    while True:
                        block=f.read(1024*1024)
                        if not block: break
                        val=zlib.crc32(block,val)
                    if val != crc: status='crc_mismatch'
            output.append({'role':role,'bytes':size,'expected_crc32':f'{crc:08X}',
                           'member':candidates[0].filename if candidates else None,'status':status})
    return {'zip':str(path), 'rom_set':'ibarablk','archive_matches_all':all(x['status'] in ('metadata_match','verified') for x in output),
            'chips':output,'uncompressed_total_bytes':sum(x[0] for x in ROM_CHIPS.values())}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('archive',type=Path)
    ap.add_argument('--verify-payload',action='store_true')
    args=ap.parse_args()
    print(json.dumps(inspect(args.archive,args.verify_payload),indent=2))
if __name__ == '__main__':main()
