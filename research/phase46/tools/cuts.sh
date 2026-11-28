#!/bin/bash
S=${RP_WORK:?set RP_WORK (see phase44 tools)}
for c in "$@"; do
  echo "=== cut after $c commands"
  bash $S/mc/build.sh MC_TEST_CUT=$c >/dev/null 2>&1
  timeout 300 bash $S/mc/kill.sh cut$c $S/mc/card_game.ps2 25 2>&1 | tail -7
done
