#!/bin/bash
# tomenu.sh : press Start until the retail Mode Select header (reference runs/t1.png) is on screen
S=${WORK:?set WORK to a work directory}
for i in $(seq 1 12); do
  $S/ctl.sh key Return 0.2; sleep 3; $S/ctl.sh shot nav
  if python3 -c "
from PIL import Image, ImageChops, ImageStat
a=Image.open('$S/runs/nav.png').convert('RGB').crop((0,0,170,60)); b=Image.open('$S/runs/t1.png').convert('RGB').crop((0,0,170,60))
import sys; sys.exit(0 if sum(ImageStat.Stat(ImageChops.difference(a,b)).mean)<30 else 1)"; then echo "at Mode Select"; exit 0; fi
done
echo "Mode Select not reached"; exit 1
