# Stage 1–5 boss damage audit

Base for the measurements is K58 at e3151c1. Use eight independent seeds per
stage and emulator, stationary player 1, shot level 2, stored rank 0x800000,
and continuous shot. Read the first positive HP and the first subsequent
zero from samples four ticks apart. A part leaving the pool at positive HP
or a stopped capture yields an unobserved kill. Keep that trial in the count.

| Stage | Target type | Subtype | HP field |
|---:|---:|---:|---|
| 1 | 5 | 0 | Part +0x3C |
| 2 | 45 | 0 | Part +0x3C |
| 3 | 51 | 0 | Part +0x3C |
| 4 | 42 | 0 | Part +0x3C |
| 5 | 65 | 0 | Part +0x3C |

The Stage 4 discovery run found a 65-HP type 41 mid-boss, then a 525-HP type 42
core. Type 58 appeared later with zero in the part HP field. The Stage 4
damage result measures type 42. It does not use type 58's arrival or departure
as evidence of an HP kill.

## MAME

Use MAME 0.276 and the user's own Black Label ROM. Start a fresh profile and
get all five stage checkpoints in one natural playthrough.

    mkdir -p runs/checkpoints runs/bl/stage1
    OUTDIR="$PWD/runs/checkpoints" mame ibarablk -rompath ROMS \
      -video none -sound none -nothrottle -drc -nonvram_save -skip_gameinfo \
      -autoboot_delay 0 -autoboot_script research/phase34/bl_checkpoints.lua

Restore from Stage 1 with the shot already held. Seed values are written once
on the first confirmed stage callback after restore, from checkpoints taken
1,000 callbacks into each stage. Use seeds 1–8 for each stage. STAGE is the
native stage byte and therefore one greater than the stage number shown.

    OUT="$PWD/runs/bl/stage1/1.txt" STAGE=2 BOSSTYPE=5 SEED=1 \
      RESUME_STATE="$PWD/runs/checkpoints/stage-1.sta" \
      mame ibarablk -rompath ROMS -video none -sound none -nothrottle -drc \
      -nonvram_save -skip_gameinfo -autoboot_delay 0 \
      -autoboot_script research/phase34/bl_boss.lua

The logger records until zero HP, the stage ends, or the sample limit is
reached. Read completed captures. Set BOSSTYPE=0 to discover parts worth at
least 50,000 points. GAUGE_HP is a diagnostic address override for a different
HP source and is unnecessary for the table above.

## PCSX2

The experimental loader uses K58's Black Label gameplay hooks and automates
stationary shot, shot level, and rank in the player update. Build it in
isolation from the production patcher.

    python3 scripts/build_ee_hooks.py --elf "Ibara (Japan).iso" \
      --define BL_DAMAGE_AUDIT --bake-elf bl_mode AUDIT.ELF
    python3 research/phase04/build_menu_probe.py "Ibara (Japan).iso" \
      --payload-elf AUDIT.ELF --label "DMG TEST" --output audit.iso

Use PCSX2 2.8.2 with PINE and a dedicated test profile. Boot DMG TEST and
enter Arcade Practice on the wanted stage. Save in slot 7 around native
tick 1,000. This is after the audit initializes and before its seed write
at tick 2,000. Use a separate output slot. The runner verifies that the
checkpoint restored and the requested seed reached the fixed tick.

    mkdir -p runs/ps2/stage1
    python3 research/phase34/ps2_trial.py --stage 1 --seed 1 --boss-type 5 \
      --pine-slot 28049 --save-file 'path/to/SLPM-66301 (F613FBE7).08.p2s' \
      --out runs/ps2/stage1/1.txt

Find the actual output filename in your dedicated profile. Keep a separate
checkpoint per stage. Start the next trial only after the prior export
finishes. Turn off frame limiting to speed up the run. Savestates stay local.

To save time on repeat trials, keep a common checkpoint closer to the boss.
It must contain no samples of the target core. Set the target before saving.
The optional --source-checkpoint and --seeded-file parameters set the RNG in
a temporary copy at that checkpoint's native tick. Point --checkpoint-slot
at the copy's slot and use the same source checkpoint for every seed in an
emulator's cohort. The recorded seed tick identifies the setup used.

## Report

    python3 research/phase34/summarize.py --bl runs/bl --ps2 runs/ps2 \
      --csv runs/boss-trials.csv

Each side uses stage1 through stage5 directories and a numbered text capture
for each seed. Report means, sample SD, observed range, and the number of
Noir results below or above the arcade range once eight kills exist per
side. The displayed clocks are MAME frame callbacks and PS2 native stage
ticks respectively. MAME uses natural entry and PCSX2 uses Practice. Equal
seed numbers choose repeatable trials within each engine. The engines are
free to consume their random streams differently.

## Initial validation

The first two PCSX2 Stage 1 trials reached zero from 168 HP in 2,548 and
2,556 native ticks. A Stage 4 pilot reached zero from 525 HP on the same
type-42 subtype-0 record in both emulators. Seed 1 took 3,692 MAME frames
and 3,568 PCSX2 ticks in these early-stage seeded pilots. The full audit
uses the repeat cohorts rather than judging parity from those pilots.

## Stage 1 seed timing control

The first arcade cohort seeded at stage callback 1,000. A second natural
checkpoint seeded at callback 3,520, about 640 callbacks before the boss.
The PS2 cohort used its common checkpoint at native tick 3,901, also about
640 ticks before the first positive boss HP. The arcade means were 2,475.5
(early) and 2,482.0 (pre-boss). On the PS2, the pre-boss cohort averaged
2,596.5. Six of its eight kills exceeded both observed arcade ranges. This
result survived the Stage 1 change in seed point.

Use CHECKPOINT_TICKS=3520 LAST_STAGE=1 with the MAME checkpoint command
to recreate the control. Choose a fresh output directory.

| Stage 1 cohort | Kills / trials | Mean | Sample SD | Range |
|---|---:|---:|---:|---:|
| MAME, early | 8/8 | 2,475.5 | 82.0 | 2,352–2,560 |
| MAME, pre-boss | 8/8 | 2,482.0 | 80.5 | 2,368–2,568 |
| PCSX2, pre-boss | 8/8 | 2,596.5 | 166.4 | 2,340–2,796 |

## Completed Stage 1–5 comparison

Each row has eight observed zero-HP finishes per side. Stage 1 uses the
arcade pre-boss control above. Stages 2–5 use the arcade checkpoints at
stage callback 1,000. PCSX2's stage-specific seed ticks were 3,901, 4,900,
7,607, 9,008, and 6,709. Starting HP agreed across both captures at all
five bosses: 168, 95, 250, 525, and 412.

| Stage | MAME mean ± SD | MAME range | Noir mean ± SD | Noir range | Noir outside arcade range |
|---:|---:|---:|---:|---:|---|
| 1 | 2,482.0 ± 80.5 | 2,368–2,568 | 2,596.5 ± 166.4 | 2,340–2,796 | 2 below, 6 above |
| 2 | 3,460.5 ± 79.4 | 3,364–3,576 | 3,624.0 ± 129.0 | 3,424–3,840 | 6 above |
| 3 | 3,083.5 ± 209.8 | 2,840–3,520 | 3,008.0 ± 161.0 | 2,728–3,268 | 1 below |
| 4 | 3,763.5 ± 171.9 | 3,624–4,164 | 3,588.0 ± 184.4 | 3,460–3,972 | 5 below |
| 5 | 3,562.0 ± 9.1 | 3,548–3,572 | 3,508.5 ± 1.4 | 3,508–3,512 | 8 below |

Stage 2 had the largest increase in mean lifetime (+163.5 ticks, 4.7%).
Stage 4 had the largest decrease (−175.5 ticks, 4.7%). Stage 5's ranges
were separated in this setup, with a much smaller mean gap (−53.5 ticks,
about 0.9 seconds). Stage 3 had the most overlap, with seven of eight PS2
kills inside the arcade range. These comparisons describe the recorded
stationary-shot trials. They leave weapon, movement, stage-entry, and
seed-point effects open.

The full Stage 4 type-58 diagnostic captured 46 samples, all zero HP.
The eight Stage 4 kills on each platform came from the type-42 core.
The isolated Stage 3 retry used the same validated checkpoint after a
savestate file disappeared briefly during replacement. The runner now
waits for a new readable ZIP archive before exporting. The report also
recognizes stage-end footer lines when a core never reached zero.

The default hook words and patch sites for bl_mode and kuro matched K58
when built with the same toolchain. The full repository test run matched
the K58 baseline in this environment (62 passed, two generated-snapshot
failures, three Phase 12 extractor setup errors). The audit build, repo
safety check, and targeted save-replacement and unobserved-kill checks
passed.
