import sys,struct; from pathlib import Path
sys.path.insert(0,'/home/user/ibara-complete/scripts'); from p2s_tools import load_ee
r=load_ee(Path(sys.argv[1])); at=int(sys.argv[2]); SZ=0x38000
def get(buf,a): o=a-0x338000 if a<0x340000 else a-0x440000+0x8000; return struct.unpack_from('<I',buf,o)[0]
pools=[('shots',0x44EA40,0x50,256),('items',0x453A40,0x58,256),('enemy',0x45A840,0xB4,192),('bullet',0x462F40,0x54,256)]
for n in range(10):
    A=r[0x01660000+n*SZ:0x01660000+(n+1)*SZ]; B=r[0x01660000+(10+n)*SZ:0x01660000+(11+n)*SZ]
    out=[]
    for a in range(0x44C380,0x44C380+0x290,4):
        if get(A,a)!=get(B,a): out.append('P1+%x:%x/%x'%(a-0x44C380,get(A,a),get(B,a)))
    for name,base,st,cnt in pools:
        nd=0;first=None
        for i in range(cnt):
            fa,fb=get(A,base+i*st),get(B,base+i*st)
            if not (fa|fb)&0x80000000: continue
            for w in range(0,st,4):
                if get(A,base+i*st+w)!=get(B,base+i*st+w):
                    nd+=1
                    if first is None: first='%s[%d]+%x:%x/%x'%(name,i,w,get(A,base+i*st+w),get(B,base+i*st+w))
        if nd: out.append('%s %d words, first %s'%(name,nd,first))
    print('upd',at+50*n,'; '.join(out[:12]))
