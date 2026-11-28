#!/bin/bash
# session.sh ISO : fresh Xvfb :50 + PCSX2 booted on ISO; leaves both running
S=${RP_WORK:?set RP_WORK, see README}
pkill -9 -f pcsx2-qt; pkill -9 Xvfb; sleep 1; rm -f /tmp/.X50-lock /tmp/.X11-unix/X50
(Xvfb :50 -screen 0 1280x960x24 -nolisten tcp >/dev/null 2>&1 &)
for i in $(seq 1 25); do DISPLAY=:50 xdotool getdisplaygeometry >/dev/null 2>&1 && break; sleep 0.2; done
rm -f $S/ext/pcsx2/build/bin/sstates/*
$S/launch.sh "$1" $S/runs/session.log
