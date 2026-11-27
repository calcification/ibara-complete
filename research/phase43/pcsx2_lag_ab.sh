#!/bin/bash
# research/phase43: run from a local PCSX2 build with pcsx2_lag_instrumentation.diff; paths are this machine's scratchpad.
# ps2ab.sh STATE OUT [LAG_AT] [LAG_BIT] : boot PCSX2 from STATE (current patched ISO); per-vsync display hashes for WAIT s
S=/tmp/claude-0/-home-user-ibara-complete/0bb67f09-7452-56ae-94ad-7b86ea619b64/scratchpad; B=$S/ext/pcsx2/build/bin; cd $B
pkill -9 -f pcsx2-qt; pkill -9 Xvfb; sleep 1; rm -f /tmp/.X50-lock /tmp/.X11-unix/X50
(Xvfb :50 -screen 0 1280x960x24 -nolisten tcp >/dev/null 2>&1 &); sleep 1
rm -f "$2"
(DISPLAY=:50 QT_QPA_PLATFORM=xcb XDG_RUNTIME_DIR=$B/run LAG_HASH="$2" LAG_AT="${3:--1}" LAG_BIT="${4:-13}" nohup ./pcsx2-qt -nogui -statefile "$1" -- $S/p12out/patched.iso > $S/lag/pcsx2.log 2>&1 &)
sleep ${WAIT:-14}
if [ -n "$SHOT" ]; then DISPLAY=:50 import -window root $SHOT; fi
pkill -9 -f pcsx2-qt
wc -l < "$2"
