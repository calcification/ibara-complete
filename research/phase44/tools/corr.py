import sys,struct; from pathlib import Path
sys.path.insert(0,'/home/user/ibara-complete/scripts'); from p2s_tools import load_ee
sym=int(open(sys.argv[1]).read().split()[0],16)
runs=[]
for f in sys.argv[2:]:
    r=load_ee(Path(f))
    def cp(w,i): return struct.unpack_from('<8I',r,0x01FC0000+w*1400*32+i*32)
    first=None
    for i in range(1200):
        if cp(0,i)[1:]!=cp(1,i)[1:] and i>0: first=i; break
    cls='A' if first and first<900 else ('B' if first else 'ok')
    A=r[0x01660000:0x01860000]; B=r[0x01860000:0x01A60000]
    runs.append((f.split('/')[-1],cls,first,A,B))
    print(f.split('/')[-1],cls,first)
skip=[(0x3459b0,0x346400),(0x341fa0,0x342000)]
for target in ('A','B'):
    cand=[]
    for o in range(0,0x200000,4):
        rel=[]
        for name,cls,first,A,B in runs:
            a,b=A[o:o+4],B[o:o+4]
            rel.append((a==b, cls==target))
        eq_t=[e for e,t in rel if t]; eq_f=[e for e,t in rel if not t]
        if eq_t and eq_f and all(not e for e in eq_t) and all(eq_f):
            a=0x300000+o
            if not any(x<=a<y for x,y in skip): cand.append(a)
    print(target,'words differing exactly in the',target,'runs:',len(cand),' '.join('%08x'%a for a in cand[:60]))
