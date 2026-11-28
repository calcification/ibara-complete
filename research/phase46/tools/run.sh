#!/bin/bash
# run.sh TAG CARD [WAIT] : boot mc.iso with CARD as slot 1, wait at the title / Mode Select, savestate, report, keep the card
S=${RP_WORK:?set RP_WORK (see phase44 tools)}; cd $S
M=$S/ext/pcsx2/build/bin/memcards/Mcd001.ps2
cp "$2" $M
./session.sh $S/mc/mc.iso >/dev/null; sleep 24; for i in 1 2 3; do ./ctl.sh key x 0.15; sleep 2; done; ./tomenu.sh >/dev/null; ./ctl.sh shot mc_${1}_menu; sleep ${3:-60}; ./ctl.sh shot mc_$1
rm -f $S/ext/pcsx2/build/bin/sstates/*; ./ctl.sh key F1 0.15; sleep 6; cp $S/ext/pcsx2/build/bin/sstates/*.p2s $S/mc/$1.p2s; pkill -9 -f pcsx2-qt; sleep 2
cp $M $S/mc/$1.card
cd /home/user/ibara-complete/scripts; python3 - "$S/mc/$1.p2s" $(cat $S/mc/sym.txt) <<'PY'
import sys,struct; from pathlib import Path; from p2s_tools import load_ee
r=load_ee(Path(sys.argv[1])); t=int(sys.argv[2],16); l=int(sys.argv[3],16)
w=struct.unpack_from('<20I',r,t); print('stage',w[1]); 
for k in range(5): print(' job %d: %s err %08x loaded %d bad %d'%(k,'done' if w[2+3*k]>>31 else '', w[2+3*k]&0x7fffffff, w[3+3*k], w[4+3*k]))
print(' mc_log', [hex(x) for x in struct.unpack_from('<4I',r,l)], 'game mc state', struct.unpack_from('<I',r,0x339d50)[0])
PY
cd /home/user/ibara-complete; python3 tools/mc_read.py $S/mc/$1.card; python3 tools/mc_read.py $S/mc/$1.card --check
