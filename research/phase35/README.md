# K58 rose form across ten more seeds

This follows the Stage 6 [Phase 33 repeat trials](../phase33/README.md). The
PS2 capture uses Phase 30 mode 3 on K58 at e3151c1. It holds shot with
stationary P1, shot level 2, and stored rank 0x800000. Seeds 5–14 extend
the prior cohort. All ten start from one Arcade Practice checkpoint and
write the LCG seed at native stage tick 10,000, before the opening core.

The timing window starts at the first positive rose-core HP sample and
ends at the first zero HP sample. Samples are four native ticks apart.
The separate [damage trace](../phase31/README.md) accounts for the full
431 HP, including a hit that can precede the first four-tick sample.
The report separates calls reaching the core from calls reaching roses
and counts intervals longer than 12 ticks between successful core hits.

Constructor frames count distinct ticks on which the rose constructor
was invoked. The attempts counter includes each invocation. Sampled
activations count newly occupied type-79 slots, including linked parts.
A single shot can contact a rose more than once. The contact/activation
ratio describes recorded contacts per occupied slot.
The constructor and activation totals run through the output save.
Contact totals use the rose-core timing window.

## Reproduction

Build the diagnostic ELF and boot its menu entry in PCSX2 2.8.2. The
batch and contact instrumentation are opt-in.

    python3 scripts/build_ee_hooks.py --elf 'Ibara (Japan).iso' \
      --define BL_ROSE_BARRAGE_TEST --define BL_ROSE_MODE=3 --define BL_ROSE_BATCH \
      --define BL_ROSE_CONTACT_TEST --define BL_SPAWN_LOG --define BL_LOG_STAGE=7 \
      --define BL_BOSS_TYPE=74 --define BL_SPAWN_RANK=0x800000u --define BL_LOCK_SHOT=2 \
      --define BL_COUNTS --bake-elf bl_mode BATCH.ELF
    python3 research/phase04/build_menu_probe.py 'Ibara (Japan).iso' \
      --payload-elf BATCH.ELF --label 'ROSE TEST' --output rose-test.iso

Select Arcade Practice Stage 6 and save in slot 7 around tick 9,200. Use
PINE with a dedicated profile and a separate slot 8 for output. Turn off
the frame limiter to speed up the replay. Substitute the slot filenames
from the test profile.

    python3 research/phase35/run_batch.py checkpoint.07.p2s capture.08.p2s runs/rose-repeat
    python3 research/phase35/report_batch.py runs/rose-repeat

The runner records the seed only after confirming the restore. It verifies
the applied seed and tick, mode, both zero-HP endpoints, contact log coverage,
and the absence of palette misses before exporting a local per-seed summary.

### Arcade spot checks

Use the [Phase 31 checkpoint procedure](../phase31/README.md) to save
at stage frame 10,500 on a natural Stage 6 entry. Replay with seeds 5 and
14, held shot, rank 0x800000, and shot level 2:

    OUTDIR=runs/bl-seed5 RESUME_STATE="$PWD/stage6.sta" SEED=5 STAGE=7 BOSSTYPE=74 \
      RANKLOCK=8388608 SHOTLOCK=2 MAXFRAMES=18000 ROSES=1 \
      mame ibarablk -rompath ROMS -drc -video none -sound none -nothrottle \
      -skip_gameinfo -autoboot_delay 0 -autoboot_script tools/stage_compare/bl_stage_log.lua

Use a separate output for seed 14. To capture contacts, switch to -nodrc
and set CONTACT_START=0 and CONTACT_TAP to the absolute path of
research/phase31/bl_contacts.lua. The two spot checks provide burst
sampling. The 17-run Phase 33 cohort provides the timing reference.
Matching seed numbers identify trials within each engine.

## Results

All ten new seeds finished with 431 traced rose-core HP and no palette
misses. Two new seeds finished below the historical arcade minimum.
The other eight fell inside the historical arcade range.

| Cohort | Runs | Mean | Sample SD | Range |
|---|---:|---:|---:|---:|
| MAME Black Label, Phase 33 | 17 | 4,053 | 438 | 3,272–4,716 |
| PCSX2 K58, Phase 33 | 5 | 3,663 | — | 3,368–4,032 |
| PCSX2 K58, seeds 5–14 | 10 | 3,650 | 302.6 | 3,228–4,016 |
| PCSX2 K58, combined | 15 | ≈3,654 | — | 3,228–4,032 |

The new cohort was 403 ticks shorter than the reported arcade mean
(9.9%). Its descriptive standard error for the difference was 143.
Adding the earlier PS2 cohort leaves a gap of approximately 399 ticks
(9.8%). The combined mean uses the rounded historical PS2 mean.

| Seed | First core | Rose core | Rose activations | Constructor frames | Rose contacts | Core contacts | HP gaps >12 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 3616 | 3332 | 4382 | 230 | 6143 | 3076 | 34 |
| 6 | 3376 | 3820 | 4796 | 264 | 7798 | 2636 | 55 |
| 7 | 3648 | 3520 | 4508 | 242 | 5912 | 3283 | 38 |
| 8 | 3916 | 3664 | 4898 | 256 | 6505 | 3225 | 45 |
| 9 | 3504 | 3800 | 4855 | 260 | 8915 | 2881 | 50 |
| 10 | 3496 | 3996 | 5196 | 281 | 8340 | 2603 | 55 |
| 11 | 3560 | 4016 | 5279 | 277 | 8656 | 3253 | 60 |
| 12 | 4108 | 3884 | 4962 | 270 | 8080 | 2687 | 52 |
| 13 | 4212 | 3240 | 4032 | 224 | 5237 | 2912 | 31 |
| 14 | 3948 | 3228 | 4288 | 222 | 5325 | 3040 | 22 |


## What could account for the gap

The PS2 recorded 69.2 constructor-active ticks per 1,000 rose-core ticks
and averaged 10.04 attempts on each active tick. The two arcade spot
checks recorded 70.6 and 70.1 distinct primary spawn frames per 1,000
rose-core frames. They averaged 8.79 and 9.19 primary activations per
spawn frame. The PS2 figure counts constructor calls and the arcade
figures count observed activations. For these runs, cadence is close.
Allocation and activation counts per burst remain worth checking
across seeds and individual attack cycles.

An interpreted arcade seed-5 replay reproduced its 3,936-frame result
with all 431 HP accounted for. It logged 5,730 rose contacts across
4,870 sampled activations (1.18 per activation), and 2,895 core contacts
(736 per 1,000 frames). The ten PS2 runs averaged 1.49 rose contacts per
sampled type-79 activation (range 1.24–1.84) and 818 core contacts per
1,000 ticks. The PS2 HP-gap count above 12 ticks varied from 22 to 60.

Both rose contacts per activation and core contacts per tick were
higher in these PS2 trials than in the one arcade contact trace.
Projectile supply, trajectories, weapon mix, and the timing of
contacts after hit flash clears are candidates. Within the PS2
cohort, more rose contacts per activation accompanied longer phases
(Pearson r = 0.80 across ten seeds). The arcade contact measurement
covers one seed.

The audit used an opt-in diagnostic ELF. The default hook words and
patch sites matched the K58 base in a rebuild with the same compiler.
