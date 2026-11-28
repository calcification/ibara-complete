#!/bin/bash
# ctl.sh key K [hold_s] | shot NAME
export DISPLAY=:50
W=$(xdotool search --onlyvisible --name Ibara | head -1)
[ -n "$W" ] && xdotool windowfocus --sync $W 2>/dev/null
case $1 in
 key) xdotool keydown $2; sleep ${3:-0.12}; xdotool keyup $2;;
 down) xdotool keydown $2;; up) xdotool keyup $2;;
 shot) import -window root -crop 340x480+150+20 ${RP_WORK:?set RP_WORK, see README}/runs/$2.png;;
esac
