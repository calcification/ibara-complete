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

## Shot cap (ported)
Per-frame alive counts: BL keeps 42–47 type-0 shots alive (slots 0–31 of its pool), PS2 Arcade 20–25 (slots 0–15).
PS2's fire routine `0x0013ACC0` caps one player at 32 slots in Arrange and 16 in Arcade (two players: 10, as in BL
`0C073830`). The BLACK LABEL build keeps 32 (`0x0013AD14` → `li v0,1`). Stage-1 boss with shot level 2: hits
mostly every 6 frames like BL; damage window 2,284 frames vs BL 2,062 (2,944 before, 3,210 originally).

## Open
* (resolved by the shot cap) Stage-1 boss damage window: PS2 2,944 frames vs BL 2,062 after the held-fire port (was 3,210). Per-frame hits:
  BL mostly every 6 frames (the flash-timer limit), PS2 spread over 6–10. Candidates: on-screen shot cap per pool
  (BL splits shots over two pools, PS2 shares one), and Arcade's per-press path (rank +16 per press).
## Who fires what (settled, `bl_shot_spawn_positions.lua`)
* **Type 0 = the ship's shot** (spawned 4 px ahead of the ship at y −8 / 0 / +4; three per volley; BL pool
  `0C2A6D9C`, PS2 shared pool). Held fire, the held speed boost and the 32-slot cap above all apply to it.
  (Earlier notes in this file that call type 0 "pods" and type 2 "main shot" had them swapped.)
* **Type 2 = the pods' weapon** (spawned at the pod positions (8, ±28) and (−20, 0)). Same speed in both games
  (8 px/frame), same alive cap (~18). PS2's pods fire ~2.3× as many shots (~165 vs ~70 per 1,000 frames).
* **BL's MG pods aim at enemies:** shot angles vary from −3.4 to +1.4 px/frame sideways with the player still. PS2's
  pod codes (handler `0x001342D8`): 0 follow the stick, **1 aim** (Arrange aim lock: target `0x00137DA0`, atan2 `0x00136CB0`; first misread as "turn back to straight ahead"), 2 fixed spread
  from table `$gp-32024` (±34°), 3/4 rotate −3/+3 per frame, 5 table `$gp-32016`. BL aims through the same kind of code (see "Pod aiming" below).
  The per-weapon pod table (`bl_player.c`) is therefore
  **disabled by default** (`BL_POD_FORMATION` to enable): writing BL's numbers into PS2's codes gave the MG pods
  a fixed spread that matches neither game.

## Pod aiming (ported, 2026-11-21)
BL pod handler `0C0779B0` (read from ibara360's annotated recompilation, study only): each pod first takes its
weapon formation's target angle (pod mode at player +0x269 + pod; stick table, fixed tables `0C182810/16`, or the
formation table `0C182834`), then, **when BL's held-shot counter +0x270 is 8**, selects a target enemy (`0C0769D0`,
previous target kept at pod +0x28) and, if there is one, sets the target angle to the atan2 from the pod to it
(`0C068E60`). So every weapon's pods aim while the shot is held, not only the MG. Turning toward the target is ±1
angle unit (of 512) per frame — every other frame in some cases (`0C2B039C` parity) — while aiming, or with the
stick formation; other formations turn by 1/16 of the gap.
PS2 equivalent: pod code 1 (above). The BLACK LABEL / KURO builds load the pod code through `pod_mode_entry`
(`ps2/hooks/bl_player.c`, at `0x001342D8`), which answers 1 while PS2's held counter `$gp-28068` (`0x00338F4C`) is
8, and points the handler's code pointer s2 at a constant 1 so the rest of the handler agrees (PS2 Arcade freezes
stick-formation pods while shot is held: the first build set targets but the angles stayed 0). Both games pick the
target the same way (keep the current one while it is targetable, flag `0x2000000`, +0xA9 ≥ +0xAB and on screen,
else round-robin from a global cursor). PCSX2 (stage 1, MG, shot held): pods on three different enemies, current
angle = target angle (25–46 / 512), pod shots 7.2 px/frame forward and ~3.3 sideways (BL: −3.4 … +1.4 sideways). Known
differences: with no enemy on screen PS2's code 1 points the pods straight ahead (BL keeps the formation angle);
PS2 Arcade turns ±1 every frame.

## Next
* Pod fire rate: PS2 pods fire ~2.3× BL's shots (per-weapon routines after the shared handler `0x00134250`:
  `0x00133750`, `0x001339F0`, `0x00133F80`, `0x00132E90`, `0x00133460`, …); measure per weapon.
* Then compare the other weapons (rocket, burner, gatling, homing, napalm, 5-way) the same way.
