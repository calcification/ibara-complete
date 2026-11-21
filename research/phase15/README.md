# Phase 15 — stage 2 (and part tables for all stages)

Runs: `tools/stage_compare/run_stage.py --stage 2 [--shot-level 2]` (rank 0x800000, invincible player holding shot).

## Part-record tables (all stages)
`tools/stage_compare/diff_part_tables.py` pairs every enemy part table the loggers saw (PS2 table read from the
retail executable, BL table dumped by MAME) and writes differing base HP into `ps2/bl_part_hp.json`, which the
BLACK LABEL build applies as preimage-checked word patches. Stages 1–2 (28 tables): only two differ —
* type 45 (stage-2 boss): core 70 → 80, the 30 armour records 20 → 50, part 0x2A 70 → 100, part 0x3C 50 → 90;
* type 8 records 06–17: 2–4 → 1.
Scores are identical everywhere. After the patches, every stage-2 type's HP distribution equals BL's.

## Stage 2 status (`stage2_spawns_shot2.txt`, `stage2_bullets_shot2.txt`, shot level 2 in both games)
* Same enemies, same order and counts, same HP; bullet speeds match per bin (e.g. 1.32/1.30/1.42 vs 1.28/1.30/1.40).
  "differs" flags on subtypes are the state-counter artefact (see Phase 14).
* **Boss (type 45, from frame ~6,500):** starts at the same time, but the PS2 fight runs ~1,000 frames longer
  (BL's final 14-type volley at 9,500–10,000, PS2's at 10,500–11,000), and at 7,500–8,000 PS2 fires 458 type-11
  bullets where BL fires 27. Post-boss parts (type 56): BL 18, PS2 6 within BL's span.
  Next: same method as stage 1 — sampler on the boss core (HP, mode bytes), no-shot timeline, then find the step
  that differs (phase length or attack choice).
* Type 8 (boss debris): PS2 spawns ~2× BL's; follows from the longer fight.

## Stage-2 boss: same logic, slower PS2 damage (2026-11-21)

Boss sampler (`--boss-type 45`, shot level 2 in both games):
* The boss's parts break in the same order in both games (0x33 and 0x31, then 0x2A, then the core); movement
  and phase timing match. The PS2 fight is longer only because each part takes ~20% longer to break, and at
  ~frame 11,400 the PS2 boss reaches its escape timer and flies off (x 106 → −94) with HP left; BL kills it first.
* Damage is applied as 1 HP per 4-frame sample in both games, and each part takes the same number of damaging
  samples (e.g. 117 for part 0x2A): the PS2 player simply lands damage on fewer samples.
* **Pod formation (ported, `ps2/hooks/bl_player.c`):** BL sets the player's three pod bytes from a per-weapon table
  on every pickup/change (BL `0C077140`, table `0C17F51B`: rocket 2,2,2 · burner 4,4,0 · gatling 0,0,0 ·
  homing 3,3,7 · napalm 1,1,1 · MG 2,2,2 · 5-way 4,4,2). PS2 has the same bytes (+0x26A..+0x26C) but Arrange fills
  them from the player-chosen formation (table `0x00212FF0`), which the BLACK LABEL build disables, so they stayed
  at 0. Pod *positions* are identical either way (±28 px beside the ship, one 28 px behind; BL pods at
  `0C2974C8`, PS2 at `0x0044C8A0 + side×0x90 + pod×0x30`). PS2's pod handler (`0x001342D8`) knows codes 0–5;
  BL's homing uses code 7, which PS2 treats as 0 — a BL addition still to port.
* With BL's codes the PS2 damage gap remains (part 0x33 now starts breaking later, the core ends lower before the
  escape). The remaining cause is most likely the **weapons themselves**: Phase 11 lists BL's player-shot routines
  as changed from arcade Ibara (`0C078F70` 578 insns, `0C077230` = PS2 projectile writer `0x0011A580`,
  `0C078E40`, `0C079600`, `0C07A410` …; table in docs/BLACK_LABEL_FEATURES.md §1b).

**Next:** port the option-weapon shot routines (start with MG, the weapon used in these tests): log the player's
projectiles in both games (type, damage field, rate) and diff, then port per weapon. Stage 1 showed the same ~10%
gap, so this is one global fix, not per-stage work.
