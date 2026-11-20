#!/usr/bin/env python3
"""Estimate high-water sparse CV1000 VRAM resident tiles from a trace.

Trace CSV: frame,op,x,y,width,height, where op is W (write) or R (read).
Frames must be nondecreasing. Rectangle footprints, not actual pixel contents.
Example: 10,W,140,400,80,120
A read of an untouched tile returns implicit zero and does not allocate.
This estimator does not emulate blitter operations or guest program logic.
"""
import argparse
import csv
import json
from pathlib import Path

EDGE = 64
W, H = 8192, 4096
TILES_X = W // EDGE
TILE_BYTES = EDGE * EDGE * 2

def estimate(path: Path, capacity: int):
    resident = set()
    per_frame = []
    active = set()
    frame = None
    ops = 0
    overflow_frame = None
    for line, row in enumerate(csv.reader(path.open(newline='')), 1):
        if not row or row[0].strip().startswith('#'):
            continue
        if line == 1 and row[0].lower().strip() == 'frame':
            continue
        if len(row) != 6:
            raise ValueError(f'line {line}: expected frame,op,x,y,width,height')
        f, operation, x, y, ww, hh = row
        f, x, y, ww, hh = map(int, (f, x, y, ww, hh))
        operation = operation.strip().upper()
        if operation not in ('W', 'R'):
            raise ValueError(f'line {line}: unknown operation {operation}')
        if ww < 0 or hh < 0 or x < 0 or y < 0 or x + ww > W or y + hh > H:
            raise ValueError(f'line {line}: rectangle outside {W}x{H} VRAM')
        if frame is not None and f < frame:
            raise ValueError(f'line {line}: frame number decreased')
        if frame is None: frame=f
        if f != frame:
            per_frame.append({'frame':frame,'touched_tiles':len(active),'resident_tiles':len(resident)})
            frame=f
            active=set()
        if ww and hh:
            for ty in range(y//EDGE, (y+hh-1)//EDGE+1):
                for tx in range(x//EDGE,(x+ww-1)//EDGE+1):
                    idx=ty*TILES_X+tx
                    active.add(idx)
                    if operation == 'W': resident.add(idx)
        ops+=1
        if overflow_frame is None and len(resident) > capacity:
            overflow_frame=f
    if frame is not None:
        per_frame.append({'frame':frame,'touched_tiles':len(active),'resident_tiles':len(resident)})
    max_active=max((x['touched_tiles'] for x in per_frame),default=0)
    return {
        'trace':str(path), 'operations':ops, 'frames_in_trace':len(per_frame),
        'resident_tiles':len(resident), 'resident_MiB':round(len(resident)*TILE_BYTES/1048576,3),
        'max_touched_tiles_per_frame':max_active,
        'max_touched_MiB_per_frame':round(max_active*TILE_BYTES/1048576,3),
        'pool_tiles':capacity, 'pool_MiB':round(capacity*TILE_BYTES/1048576,3),
        'overflow_first_frame':overflow_frame, 'fits_without_eviction':overflow_frame is None,
        'frame_metrics':per_frame,
        'limitations':['This approximates footprint at 64x64 tile granularity',
                       'No replacement/eviction policy is modeled',
                       'Written rectangles are assumed nonzero; zero-only writes may overestimate',
                       'Only covered regions are counted; trace completeness determines accuracy']
    }

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('trace',type=Path)
    ap.add_argument('--pool-mib',type=int,default=8)
    ap.add_argument('--output',type=Path)
    args=ap.parse_args()
    if args.pool_mib<1 or args.pool_mib>64: ap.error('pool must be 1–64 MiB')
    summary=estimate(args.trace,args.pool_mib*1048576//TILE_BYTES)
    body=json.dumps(summary,indent=2)
    if args.output: args.output.write_text(body+'\n')
    else: print(body)
if __name__ == '__main__': main()
