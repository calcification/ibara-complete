#!/bin/bash
# build.sh : replay experiment ISO (temporary wiring; restores the tree)
S=${RP_WORK:?set RP_WORK, see README}; cd /home/user/ibara-complete
cp ps2/hooks/replay.c $S/rp/replay.keep2; cp scripts/build_ee_hooks.py $S/rp/beh.keep; cp ps2/hooks/kuro.c $S/rp/kuro.c.keep; cp ps2/prebuilt/kuro.json $S/rp/kuro.keep; cp ps2/prebuilt/bl_mode.json $S/rp/bl.keep
python3 - <<'PY'
p='scripts/build_ee_hooks.py'
s=open(p).read()
a='"bl_select_data.c", "bl_glow_data.c", "arcade_slowdown.c", "game_start.c", "rpl.c"],'
assert s.count(a)==1; s=s.replace(a,'"bl_select_data.c", "bl_glow_data.c", "arcade_slowdown.c", "game_start.c", "rpl.c", "replay.c"],')
b='"sym_patches": RANK_OPTION_PATCHES + PRACTICE_MODE_PATCHES + KURO_PATCHES,'
assert s.count(b)==1
s=s.replace(b,'"sym_patches": RANK_OPTION_PATCHES + PRACTICE_MODE_PATCHES + KURO_PATCHES,')
c='"defines": ["KURO_PRESENTATION", "ARCADE_SLOWDOWN_CONFIG", "SLOWDOWN_HARDWARE"],'
assert s.count(c)==1; s=s.replace(c,'"defines": ["KURO_PRESENTATION", "ARCADE_SLOWDOWN_CONFIG", "SLOWDOWN_HARDWARE", "REPLAY_BUILD"],')
open(p,'w').write(s)
PY

sed -i "1i #define RP_FIRST_MODE 2u\n#define RP_SNAP_AT ${SNAP:-925}u${EXTRA}" ps2/hooks/replay.c; rm -f $S/rp/rp.iso
python3 scripts/build_black_label_iso.py "$S/iso/Ibara (Japan).iso" --output $S/rp/rp.iso --bl-rom $S/blk/ibarablk.zip 2>&1 | grep -iE "rror|assert"
python3 -c "
import sys,tempfile; sys.path.insert(0,'scripts')
import build_ee_hooks as h
from pathlib import Path
b=h.build_hook('kuro',Path(tempfile.mkdtemp()),h.BAKE_BASE,h.BAKE_END)
print(hex(b['syms']['rp']))" > $S/rp/sym.txt
cp $S/rp/beh.keep scripts/build_ee_hooks.py; cp $S/rp/kuro.c.keep ps2/hooks/kuro.c; cp $S/rp/kuro.keep ps2/prebuilt/kuro.json; cp $S/rp/bl.keep ps2/prebuilt/bl_mode.json
cp $S/rp/replay.keep2 ps2/hooks/replay.c; cat $S/rp/sym.txt
