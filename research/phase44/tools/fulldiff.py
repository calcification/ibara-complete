import sys,struct; from pathlib import Path
sys.path.insert(0,'/home/user/ibara-complete/scripts'); from p2s_tools import load_ee
r=load_ee(Path(sys.argv[1]))
A=r[0x01660000:0x01860000]; B=r[0x01860000:0x01A60000]
d=[0x300000+i for i in range(0,0x200000,4) if A[i:i+4]!=B[i:i+4]]
skip=[(0x3459b0,0x346400),(0x341fa0,0x342000),(0x33ee00,0x33f700)]
d=[x for x in d if not any(a<=x<b for a,b in skip)]
g=[]
for x in d:
    if g and x-g[-1][1]<=0x20: g[-1][1]=x; g[-1][2]+=1
    else: g.append([x,x,1])
print(len(d),'words in',len(g),'groups')
for a,b,n in g[:80]:
    o=a-0x300000; print('  %08x-%08x %4d  %08x/%08x'%(a,b,n,struct.unpack_from('<I',A,o)[0],struct.unpack_from('<I',B,o)[0]))
