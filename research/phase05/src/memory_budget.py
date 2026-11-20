#!/usr/bin/env python3
"""Illustrative PS2 memory allowance for a possible arcade Ibara Kuro runtime.
Numbers other than hardware capacities are engineering allocations, not measurements.
"""
import argparse
import json

MAIN_RAM = 32
ALLOCATIONS = {
    'CV1000 work RAM': 8.0,                 # runtime/recomp.h
    'Sparse VRAM 64x64 tile pool': 8.0,     # proposed, unverified
    'U4 program ROM': 2.0,                  # romload.c
    'NAND 64-page read cache': 64*2112/1048576,
    '320x240 16-bit double buffers': 320*240*2*2/1048576,
    'Audio ring buffer': 0.5,              # proposed, unverified
}

def report(vram_mib=8):
    d=dict(ALLOCATIONS)
    d['Sparse VRAM 64x64 tile pool'] = float(vram_mib)
    total=sum(d.values())
    return {
        'hardware_memory_MiB':MAIN_RAM,
        'allocation_budget_MiB':{k:round(v,4) for k,v in d.items()},
        'allocated_MiB':round(total,4),
        'unallocated_MiB':round(MAIN_RAM-total,4),
        'note':'Unallocated budget still must cover compiled game code, heaps, stacks, PS2 libraries, DMA structures, textures and any resident frontend. This is NOT a game memory measurement.',
        'rom_not_resident':'U2 132 MiB NAND and two 4 MiB YMZ sound ROMs would require streaming/reuse. No actual streaming performance is established.',
        'vram_warning':'64 MiB arcade VRAM cannot be directly mapped into 32 MiB EE memory; sparse tiling requires rewriting all direct VRAM accesses and trace-based peak validation.',
        'fits_illustrative_base':total<=MAIN_RAM
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vram-mib',type=int,default=8)
    args=p.parse_args()
    print(json.dumps(report(args.vram_mib),indent=2))
if __name__=='__main__':main()
