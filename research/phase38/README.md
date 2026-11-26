# Stage 1–5 boss damage audit with matched pods

Gameplay is K60. The audit is based on the post-K60 handoff at f2cfc73.
The procedure follows Phase 34 with the same locked rank (0x800000),
shot level (2), stationary player 1, held shot, core IDs, four-update HP
sampling and eight trial seeds per stage. MAME is 0.276 and PCSX2 is
2.8.2. MAME enters through natural play. PCSX2 enters through Practice.
Matching seed labels makes replays repeatable within each engine.

The new MAME trace records the three native pod-kind bytes and the
selected weapon from P1 +0x26C through +0x26F on restore and whenever
they change. The PS2 diagnostic equips those bytes at P1 +0x26D through
+0x270 and updates the active pod records. Equip before taking the
pre-boss checkpoint. Leave the pods alone after equipping and check
the weapon, count, per-pod player bytes and active pod records each
update. The export fails if it observes a mismatch.

## Reproduction

Use the [Phase 34 procedures](../phase34/README.md) for natural MAME
checkpoints, the Stage 1 late checkpoint and the PS2 test menu. For
the MAME boss command set TRACE_LOADOUT=1, then check that the same
loadout remains active through all eight trials for the stage.
Build the PS2 payload with both defines.

    python3 scripts/build_ee_hooks.py --elf 'Ibara (Japan).iso' \
      --define BL_DAMAGE_AUDIT --define BL_DAMAGE_AUDIT_MATCH_PODS \
      --bake-elf bl_mode AUDIT.ELF

For late PS2 checkpoints, save while three Practice pods are already
deployed and before the target has positive HP. Use --source-checkpoint
and --seeded-file alongside --loadout 12,12,12,6. The trial sets the RNG
in the temporary state and equips the requested pods at the first
native player update on restore. The early checkpoint runner waits for
three active pods before equipping; it needs that to happen before the
fixed seed tick.

    python3 research/phase34/summarize.py --bl runs/bl --ps2 runs/ps2 \
      --match-loadout --csv runs/boss-trials.csv

The report verifies a stable arcade loadout and matching PS2 loadout
for each paired stage. Its range comparison uses the observed eight
arcade kills for that stage.

To reuse the Phase 34 arcade cohort, put any fresh arcade checkpoint
traces in their own directory and point --bl-loadout-reference at it.
Compare the repeated HP curves against their Phase 34 counterparts
before combining the reference trace with the original cohort.
