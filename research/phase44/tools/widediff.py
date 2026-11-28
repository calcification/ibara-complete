import sys,struct; from pathlib import Path
sys.path.insert(0,'/home/user/ibara-complete/scripts'); from p2s_tools import load_ee
r=load_ee(Path(sys.argv[1])); SZ=0x220000
A=r[0x01660000:0x01660000+SZ]; B=r[0x01660000+SZ:0x01660000+2*SZ]
def addr(o): return 0x280000+o if o<0x200000 else 0x01F00000+o-0x200000
skip=[(0x3459b0,0x346400),(0x341fa0,0x342000),(0x33ee00,0x33f700)]
d=[o for o in range(0,SZ,4) if A[o:o+4]!=B[o:o+4] and not any(x<=addr(o)<y for x,y in skip)]
g=[]
for o in d:
    if g and o-g[-1][1]<=0x20: g[-1][1]=o; g[-1][2]+=1
    else: g.append([o,o,1])
print(len(d),'words',len(g),'groups')
for a,b,n in g[:70]: print('  %08x-%08x %4d %08x/%08x'%(addr(a),addr(b),n,struct.unpack_from('<I',A,a)[0],struct.unpack_from('<I',B,a)[0]))
