#!/bin/bash
# launch.sh ISO LOG : start pcsx2 on :50, relaunch until the game ELF is reported
S=${WORK:?set WORK to a work directory}; B=$S/ext/pcsx2/build/bin; cd $B
for a in 1 2 3 4 5 6; do
  pkill -9 -f pcsx2-qt; sleep 1
  (DISPLAY=:50 QT_QPA_PLATFORM=xcb XDG_RUNTIME_DIR=$B/run nohup ./pcsx2-qt -nogui -fastboot -- "$1" > "$2" 2>&1 &)
  for i in $(seq 1 20); do sleep 1; grep -aq "ELF (cdrom0" "$2" && pgrep -f pcsx2-qt >/dev/null && { echo "booted (attempt $a)"; exit 0; }; pgrep -f pcsx2-qt >/dev/null || break; done
done; echo "failed to boot"; exit 1
