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

## Shot pools and the held boost (BL ↔ PS2)
* BL has two shot pools of 0x34-byte records: `0C2380D0` (type 2, streams +8 1..4) and `0C2A6D9C` (32 per side:
  type 0 shots, spawned by `0C073830`, plus their impact "burst" records +8 0xA..0xD at 2.25 px/frame). PS2 keeps
  both kinds in one pool from `0x0044C9C0`; PS2's collision for them (`0x0012B660`) also slows shots on impact.
* BL `+0x270` is the held-shot frame counter (0..8, reset on release; `bl_held_counter.lua`). When it is 8, the
  type-0 spawner adds half the speed (13.5 instead of 9 px/frame). PS2's fire routine `0x0013ACC0` has the same rule
  on its own held counter (`$gp-28068`, `0x0013AECC`), which Arcade used to reset every frame; the held-fire patch
  above makes it count, so the boost now applies in the BLACK LABEL build too.

## Open
* Stage-1 boss damage window: PS2 2,944 frames vs BL 2,062 after the held-fire port (was 3,210). Per-frame hits:
  BL mostly every 6 frames (the flash-timer limit), PS2 spread over 6–10. Candidates: on-screen shot cap per pool
  (BL splits shots over two pools, PS2 shares one), and Arcade's per-press path (rank +16 per press).
* Option-pod weapons (MG etc.): PS2's pods fire type-0 shots on the 8-frame beat; in BL the type-0 shots come from
  the same spawner as above. Which object fires them in BL (ship or pods) is not yet settled.
