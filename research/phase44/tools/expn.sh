#!/bin/bash
# expn.sh TAG : Noir Practice: game 1 (ignored), game 2 recorded with scripted inputs, game 3 played back
S=${RP_WORK:?set RP_WORK, see README}; cd $S
k(){ ./ctl.sh key $1 ${3:-0.15}; sleep ${2:-1}; }
sel(){ sleep 9; ./ctl.sh shot ${1}; k x 2; k x 2; k x 2; k x 6; ./ctl.sh shot ${1}s; }   # loading, ship select
ret(){ k Return 1.5; ./ctl.sh shot ${1}p; k Down 0.8; k Down 0.8; k x 6; ./ctl.sh shot ${1}m; }
./session.sh $S/rp/rp.iso >/dev/null; sleep 24; ./tomenu.sh >/dev/null; k Down; k Down; k x 3; k Down; k x 3
k x 1; sel ${1}_1; sleep 4; ret ${1}_1
k x 1; sel ${1}_2
./ctl.sh down z; for i in $(seq 1 ${LOOPS:-3}); do k Left 1 0.8; k Up 1 0.5; k Right 1 1.2; k Down 1 0.5; done; ./ctl.sh up z
ret ${1}_2
k x 1; sel ${1}_3; sleep ${PLAYWAIT:-50}; ./ctl.sh shot ${1}_3e
rm -f $S/ext/pcsx2/build/bin/sstates/*; ./ctl.sh key F1 0.15; sleep 6; cp $S/ext/pcsx2/build/bin/sstates/*.p2s $S/rp/$1.p2s; pkill -9 -f pcsx2-qt
cd /home/user/ibara-complete/scripts; python3 - "$S/rp/$1.p2s" $(awk '{print $1}' $S/rp/sym.txt) <<'PY2'
import sys, struct; from pathlib import Path; from p2s_tools import load_ee
r=load_ee(Path(sys.argv[1])); a=int(sys.argv[2],16)
magic,mode,nu,pu,ovf,c0,c1,miss,pd,s0,f0,g0,g1,g2,g3,fm=struct.unpack_from('<16I',r,a)
print('mode %d updates %d played %d overflow %d cps %d/%d tick_miss %d first_miss %d done %d'%(mode,nu,pu,ovf,c0,c1,miss,fm if fm<2**31 else -1,pd))
def cp(w,i): return struct.unpack_from('<8I',r,0x01FC0000+w*1400*32+i*32)
A={cp(0,i)[0]:cp(0,i) for i in range(c0)}; B={cp(1,i)[0]:cp(1,i) for i in range(c1)}
ks=sorted(set(A)&set(B)); bad=[k for k in ks if A[k]!=B[k]]
print('updates compared', len(ks), 'mismatches', len(bad))
for k in bad[:4]: print('  upd', k, A[k], B[k])
if ks: print('last', A[ks[-1]], B[ks[-1]])
PY2
