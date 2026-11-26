# Moving homing pods and target changes

This follows the [Phase 36 pod census](../phase36/README.md) on K60.
MAME 0.276 and PCSX2 2.8.2 each use the Stage 2 route, held shot,
weapon 3, shot level 2, rank 0x800000, and seed 1. At about 2,400
stage updates the fixture applies 20 updates of each of the eight
directions, with no direction at the start and end. It records 800
updates of three pod records in each run. The arcade sees controller
directions through MAME input fields. The PS2 fixture injects the
corresponding processed input bits. Position changes confirmed both
engines moved along the same axes with each input in this profile.

Build the opt-in prototype, which supports switching the fallback
and enemy pool control on each replay.

    python3 scripts/build_ee_hooks.py --elf 'Ibara (Japan).iso' \
      --define BL_POD_AUDIT --define BL_POD_AUDIT_FALLBACK --define BL_POD_AIM_TRACE \
      --bake-elf bl_mode AIM.ELF
    python3 research/phase04/build_menu_probe.py 'Ibara (Japan).iso' \
      --payload-elf AIM.ELF --label 'POD AIM' --output pod-aim.iso

Boot POD AIM and use Arcade Practice Stage 2. Enable PINE, save the
unarmed Stage 2 checkpoint in slot 7 near native tick 900, then run
the trace with the paths to slots 7 and 8. Keep the frame limit off
for fast playback.

    python3 research/phase39/ps2_homing.py slot07.p2s slot08.p2s runs/aim

For MAME use the Phase 36 natural Stage 2 checkpoint. Repeat with
POD_EMPTY=1 and OUT=runs/aim/bl-empty.csv. The live run uses the
regular enemy pool.

    RESUME_STATE="$PWD/stage-2.sta" OUT=runs/aim/bl-live.csv \
      mame ibarablk -rompath ROMS -drc -video none -sound none -nothrottle \
      -skip_gameinfo -autoboot_delay 0 -autoboot_script research/phase39/bl_homing.lua
    python3 research/phase39/summarize.py runs/aim

## What the traces show

A target ID of 192 means no target in these traces. Offsets +36 and
+38 of the 48-byte pod record are current and desired heading, in
512 units per turn. Desired heading in the empty arcade follows
this table.

| D-pad | Bits | First pod | Second pod | Center |
|---|---:|---:|---:|---:|
| None | 0 | 288 | 224 | 0 |
| Up | 1 | 288 | 224 | 256 |
| Up-left | 5 | 288 | 224 | 192 |
| Left | 4 | 288 | 224 | 128 |
| Down-left | 6 | 288 | 224 | 64 |
| Down | 2 | 288 | 224 | 0 |
| Down-right | 10 | 288 | 224 | 448 |
| Right | 8 | 288 | 224 | 384 |
| Up-right | 9 | 288 | 224 | 320 |

Stock K60 aims all three directly ahead in the cleared-enemy run.
The prototype matched 2,391 of 2,400 arcade formation headings in the
cleared-enemy PS2 run. The nine differences are the center pod's
first update after each input change. It still reports the previous
direction's heading on that update, then the new heading. The live
prototype matched the formation heading on all 366 no-target samples
and recorded six acquisitions and six losses. MAME recorded nine
acquisitions and nine losses across the three pods. The enemies and
target slots can diverge between engines, so these counts describe
transitions witnessed in the trace.

The arcade center pod lost target 27 while moving up-left at trace
tick 59 and immediately set desired heading to 192. In the PS2
prototype the center pod lost target 0 at tick 609, set the stationary
heading to 0, acquired target 11 at tick 727, and turned toward native
heading 25. Its actual heading moved from 0 to 8 on acquisition.
The prototype changes desired heading on the no-target branch and
lets the existing steering behavior turn the pod.

## Release integration

The opt-in code tests the branch at 0x00134368 without changing the
delay-slot store or the native target lookup. Use the guard on the
returned target index and homing weapon when moving the correction
to the Noir release profile. The diagnostic follows P1 only and uses
one Stage 2 seed. Release checks still include P2, other pod weapons
and actuator orientation. The default baked words and sites for
bl_mode and kuro match K60.
