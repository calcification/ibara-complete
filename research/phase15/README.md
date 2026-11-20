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
