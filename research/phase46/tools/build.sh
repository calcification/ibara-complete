#!/bin/bash
# build.sh [extra defines...] : memory card test ISO $S/mc/mc.iso (mcfile.c + mctest.c, MC_TEST); restores the tree
S=${RP_WORK:?set RP_WORK (see phase44 tools)}; cd /home/user/ibara-complete
cp scripts/build_ee_hooks.py $S/mc/beh.keep; cp ps2/prebuilt/kuro.json $S/mc/kuro.keep; cp ps2/prebuilt/bl_mode.json $S/mc/bl.keep
python3 - "$@" <<'PY'
import sys
p='scripts/build_ee_hooks.py'; s=open(p).read()
a='"arcade_slowdown.c", "game_start.c"],'
assert s.count(a)==1; s=s.replace(a,'"arcade_slowdown.c", "game_start.c", "mcfile.c", "mctest.c"],')
c='"defines": ["KURO_PRESENTATION", "ARCADE_SLOWDOWN_CONFIG", "SLOWDOWN_HARDWARE"],'
assert s.count(c)==1; s=s.replace(c,'"defines": ["KURO_PRESENTATION", "ARCADE_SLOWDOWN_CONFIG", "SLOWDOWN_HARDWARE", "MC_TEST"'+''.join(', "%s"'%d for d in sys.argv[1:])+'],')
open(p,'w').write(s)
PY
rm -f $S/mc/mc.iso
python3 scripts/build_black_label_iso.py "$S/iso/Ibara (Japan).iso" --output $S/mc/mc.iso --bl-rom $S/blk/ibarablk.zip 2>&1 | grep -iE "rror|assert|warn"
python3 -c "
import sys,tempfile; sys.path.insert(0,'scripts')
import build_ee_hooks as h
from pathlib import Path
b=h.build_hook('kuro',Path(tempfile.mkdtemp()),h.BAKE_BASE,h.BAKE_END)
print(hex(b['syms']['mc_test']), hex(b['syms']['mc_log']), b['size'])" > $S/mc/sym.txt
cp $S/mc/beh.keep scripts/build_ee_hooks.py; cp $S/mc/kuro.keep ps2/prebuilt/kuro.json; cp $S/mc/bl.keep ps2/prebuilt/bl_mode.json
cat $S/mc/sym.txt
