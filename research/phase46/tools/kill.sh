#!/bin/bash
# kill.sh TAG CARD SECONDS : boot mc.iso, reach Mode Select, wait SECONDS, kill PCSX2 (power cut), check the card
S=${RP_WORK:?set RP_WORK (see phase44 tools)}; cd $S
M=$S/ext/pcsx2/build/bin/memcards/Mcd001.ps2
cp "$2" $M
./session.sh $S/mc/mc.iso >/dev/null; sleep 24; for i in 1 2 3; do ./ctl.sh key x 0.15; sleep 2; done; ./tomenu.sh >/dev/null
sleep $3; pkill -9 -f pcsx2-qt; sleep 2; cp $M $S/mc/$1.card
cd /home/user/ibara-complete; python3 $S/mc/verify.py $S/mc/card_game.ps2 $S/mc/$1.card
