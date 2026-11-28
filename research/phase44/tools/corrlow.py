import sys,struct; from pathlib import Path
sys.path.insert(0,'/home/user/ibara-complete/scripts'); from p2s_tools import load_ee
runs=[]
for f in sys.argv[1:]:
    r=load_ee(Path(f))
    def cp(w,i): return struct.unpack_from('<8I',r,0x01FC0000+w*1400*32+i*32)
    first=None
    for i in range(1,1200):
        if cp(0,i)[1:]!=cp(1,i)[1:]: first=i; break
    cls='A' if first and first<900 else ('B' if first else 'ok')
    A=r[0x01660000:0x01780000]; B=r[0x01780000:0x018A0000]
    runs.append((f.split('/')[-1],cls,first,A,B)); print(f.split('/')[-1],cls,first)
def addr(o): return 0x200000+o if o<0x100000 else 0x01F00000+o-0x100000
for target in ('A','B'):
    cand=[]
    for o in range(0,0x120000,4):
        t=[A[o:o+4]==B[o:o+4] for n,c,f,A,B in runs if c==target]
        u=[A[o:o+4]==B[o:o+4] for n,c,f,A,B in runs if c!=target]
        if t and u and not any(t) and all(u): cand.append(o)
    print(target,len(cand))
    for o in cand[:40]:
        print('  %08x'%addr(o),' '.join('%s:%08x/%08x'%(c,struct.unpack_from('<I',A,o)[0],struct.unpack_from('<I',B,o)[0]) for n,c,f,A,B in runs))
