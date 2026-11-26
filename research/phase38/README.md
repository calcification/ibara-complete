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
+0x270 and updates the active pod records. It checks the weapon,
count, per-pod player bytes and active pod records after each player
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

## Results

Every stage's arcade checkpoint held weapon 6 with three kind-12
(5-way) pods. Sixteen MAME retraces verified that loadout through the
HP-zero endpoint, with eight runs for Stage 1 and two per stage for
Stages 2–5. Their HP sample rows reproduced Phase 34 exactly. The
arcade range below uses the full Phase 34 eight-seed cohort for each
stage. All 40 new K60 PS2 exports checked the matched loadout with
zero mismatched updates. Stage 1–3 loadouts were injected on restore
at ticks 3,900, 4,914 and 7,603 respectively. Stage 4 and 5 already
had three active pods when equipped at ticks 133 and 131. Their
seeded checkpoints were at ticks 9,010 and 6,706.

A failed Stage 1 setup had equipped too early, while native Practice
still initialized its pods. The measured loadout reverted to kind 10
and that entire batch was discarded. The completed cohort equips
after restoring a checkpoint that already has three active pods.

Eight observed zero-HP finishes per engine and stage. Time is from
the first positive part HP sample to the first zero sample in MAME
frame callbacks or PS2 native ticks. Both engines started at
168, 95, 250, 525 and 412 HP respectively.

| Stage | BL kills / trials | BL mean | BL SD | BL range | Noir kills / trials | Noir mean | Noir SD | Noir range | Noir vs BL range |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 8/8 | 2482.0 | 80.5 | 2368–2568 | 8/8 | 2459.0 | 27.7 | 2416–2500 | 0 below, 0 above |
| 2 | 8/8 | 3460.5 | 79.4 | 3364–3576 | 8/8 | 3494.5 | 29.7 | 3440–3544 | 0 below, 0 above |
| 3 | 8/8 | 3083.5 | 209.8 | 2840–3520 | 8/8 | 3106.5 | 247.0 | 2968–3704 | 0 below, 1 above |
| 4 | 8/8 | 3763.5 | 171.9 | 3624–4164 | 8/8 | 3771.0 | 185.8 | 3644–4200 | 0 below, 1 above |
| 5 | 8/8 | 3562.0 | 9.1 | 3548–3572 | 8/8 | 3508.0 | 0.0 | 3508–3508 | 8 below, 0 above |

Stages 1 and 2 are fully inside the observed arcade range. Stage 3
has one trial at 3,704 against an arcade maximum of 3,520. Stage 4 has
one at 4,200 against a maximum of 4,164. Stage 5 is consistently 54
updates faster on average (1.5%, about 0.9 s). Every stage mean is
within 1.6%. These runs support keeping the current boss damage
values. Further Stage 5 timing work can begin with the first frames
at which HP actually decreases. The [per-seed CSV](results.csv)
contains all 80 outcomes.

The default bl_mode and kuro baked hooks match K60's words and sites.
The EE and patcher tests recorded 24 passes. The two generated-artifact
checks for bl_mode and the XTC PNACH fail with the same cross toolchain
on the clean handoff commit.
