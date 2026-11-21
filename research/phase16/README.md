# Phase 16 — player weapons: firing, hits, damage

Tools: `tools/stage_compare/run_stage.py` with `--define BL_CORE_EVERY BL_CORE_HIT BL_CORE_ONLY0 BL_SHOT_LOG`
(PS2: boss core HP and hit timer every frame, every new player shot) and `EVERY=1 HIT=1 SHOTS=1` for MAME.

## Damage model (both games)
* Regular player shots: records of 0x34 bytes (BL from `0C2380D0`, PS2 from `0x0044C9C0`; flags `C…`, +4 type,
  +8 stream, x/y +0x10/+0x14, velocity +0x18/+0x1C). BL's shot-vs-enemy (`0C06E540`) passes damage 1 per hit.
* Damage routine (BL `0C0A8E90`, changed vs arcade; PS2 `0x001278B0`): a hit arms the part's flash timer `+0x84` = 6
  and a part loses at most one hit's damage per flash cycle (BL: per-cycle cap in `+0x3E`, which PS2 uses on its
  Arrange path; PS2 Arcade blocks hits until the timer is 0). Measured per frame: BL's held fire lands a hit every
  **6** frames (timer 6→1 then hit), PS2 every **8**. Switching PS2 to the Arrange damage path changed nothing, so
  the difference is how often shots arrive, not the rule (patch not kept).

## Held fire (ported)
* BL, shot held: fires every **2** frames, pausing only while the on-screen shot cap is full (`bl_tap_modes.lua`,
  per-frame shot logs). The arcade games have no auto-fire beyond this; ibara360's 7.5 Hz "AUTO SHOT" is an emulator
  feature.
* PS2 shooter `0x0013B2F0`: Arcade fires held shots every `+0x262` frames (8); Arrange, after 8 held frames, every
  2 — BL's rule. The BLACK LABEL build takes the held-frame path in Arcade (`0x0013B310` `lw v1,$gp-28076` →
  `li v1,1`). New presses still run Arcade's press path (rank harder by 16 per press, `0x00129DF0`): BL's rule for
  that is not yet checked.
* Result, stage-1 boss: PS2 main-shot streams (type 2, +8 1..4) now 176 per 2,000 frames vs BL 140; boss damage
  window 2,944 frames (was 3,210; BL 2,062).

## Open: option pods
PS2's three MG pods fire type-0 shots (+8 0 and 3, 560 per 2,000 frames). BL's pods produce no shots in that
pool while held, yet BL deals more damage, so BL's pod weapons work differently (another pool, or only while the
pods are "out" — BL's XTC rule also mentions pods being out). Next: find BL's pod-weapon shots (write taps from the
pod objects at `0C2974C8`) and compare with PS2's MG.
