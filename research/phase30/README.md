# Stage 6 rose count and barrage probe

Base build K55 at a5d7b538. This is a separate PCSX2 measurement build. The normal
K55 ISO patch and prebuilt hook files come from the base branch.

## What the trace isolated

The Black Label write trace grouped type-14 stores by the saved return address of
the bullet emitter at 0x0C0BA970. The shortcut run saw 1,523 stores using pattern
0x0C189C9C from the rose helper (return PC 0x0C0A2C4C), between stage-relative frames
17,670 and 21,873. The separate 3,084 type-14 stores at return PC 0x0C0A439A occurred
before the rose phase. The two sibling rose loops also have matching emitter calls
in the listing (return PCs 0x0C0A2EB2 and 0x0C0A316E).

The PS2 equivalent emitter is 0x00123950. The probe runs the retail rose constructor
first, then uses that emitter at the same position and angle with one shot and the
measured 2.75 px/tick base speed. It checks that the native palette selects type 14
and records emitter calls and palette misses separately from observed activations.

There are two distinct rank inputs. Noir already replaces the shared firing timer
at 0x00122120 with Black Label's stage-adjusted rule. The group-size initialization
still shifts the raw rank at 0x00178DE8, 0x00178EB4 and 0x00179058. All three analogous
Black Label paths instead subtract the stage/difficulty bias before shifting rank by
20. With rank 0x800000, stage byte 7 and difficulty byte 3, group size is 7 in
retail Noir and 10 in Black Label. The probe can adjust that input independently of
the barrage. This corrects the earlier interpretation that the three call sites
used the retail timer in the full Noir build.

## Reproduction

Build a separate Stage 6 logger disc from a clean Ibara ISO. The controls are in
RAM and the probe uses the default Black Label difficulty byte 3.

    python3 scripts/build_ee_hooks.py --elf "Ibara (Japan).iso" \
      --define BL_ROSE_BARRAGE_TEST --define BL_SPAWN_LOG --define BL_LOG_STAGE=7 \
      --define BL_BOSS_TYPE=74 --define BL_SPAWN_RANK=0x800000u --define BL_LOCK_SHOT=2 \
      --define BL_COUNTS --bake-elf bl_mode ROSE_TEST.ELF
    python3 research/phase04/build_menu_probe.py "Ibara (Japan).iso" \
      --payload-elf ROSE_TEST.ELF --label "ROSE TEST" --output rose-test.iso

Boot the logger disc in PCSX2 and select the ROSE TEST entry, then Arcade Practice,
Stage 6. The probe applies a constant P1 shot input before the native player update.
Use a dedicated emulator profile and save at around native stage tick 10,900, before
the first core at tick ~12,104. On each restore, verify stage byte 7 at 0x00338E9C,
the tick at 0x00338EA0, magic 0x31534F52 at 0x01F5E000, and zero rose attempts at
0x01F5E008. Write the trial mode as a 32-bit word at 0x01F5E004.

| Mode | Barrage | Adjusted group size |
|---:|---|---|
| 0 | Off | Off |
| 1 | On | Off |
| 2 | Off | On |
| 3 | On | On |

Keep a separate save for each run after the rose core reaches 0 HP. Analyze only
captures made with this probe and retain the boot checkpoint for repeats.

    python3 research/phase30/report_roses.py --mame-trace type14.txt \
      --mame-run runs/mame-stage6 baseline.p2s barrage.p2s groups.p2s combined.p2s

For the MAME caller trace use the Phase 26 type-14 trace command. For a full timed
MAME run use tools/stage_compare/bl_stage_log.lua with STAGE=7, BOSSTYPE=74,
RANKLOCK=8388608, SHOTLOCK=2 and MAXFRAMES=130000. Omit QUICK_S6 for timed runs.
The PS2 uses a Practice entry. The MAME full run advances through Stages 1–5.
Use the first form as a control for the starting shot exposure before comparing
the rose results across emulators.

## Results

| Run | First core elapsed | Rose core elapsed | Type-79 activations | Type-14 activations during rose core |
|---|---:|---:|---:|---:|
| Black Label, natural Stage 6 (two identical MAME runs) | 5,492 | 3,272 | 4,149 | 1,986 |
| PS2 baseline | 3,824 | 3,296 | 2,962 | 0 |
| PS2 barrage only | 3,824 | 3,032 | 2,866 | 1,375 |
| PS2 adjusted group size only | 3,824 | 3,476 | 4,565 | 0 |
| PS2 combined, including the PINE runner repeat | 3,824 | 3,712 | 4,852 | 2,386 |

Elapsed means first sampled positive HP to first sampled zero HP. MAME uses its
frame callback clock and PS2 uses native stage ticks. Both log cores every four
samples. Type-14 counts are sampled activations in the indicated core interval.
PS2 reports its emitter attempts separately. The combined run called the emitter
2,539 times with zero palette misses.

Both clean MAME launches produced byte-identical spawn, bullet and core logs.
The PS2 repeats of modes 0, 1 and 3 reproduced all headline values in the table.
The initially attempted mode-3 restore raced the host write and actually ran
mode 0. The verified repeat used run_trial.py, which waits for the probe control
block to restore, then checks that the selected mode persists.

    python3 research/phase30/run_trial.py checkpoint.p2s \
      --checkpoint-slot 7 --save-slot 5 --mode 3

The combined build reaches 1.36 type-79 activations per tick while roses are spawning,
against 1.32 per MAME frame (+3.2%). Type-14 activations per rose-core tick/frame are
0.643 vs 0.607 (+5.9%). The phase lasts 440 ticks longer (+13.4%) and produces 703
more type-79 activations (+16.9%). The combined change stays in the diagnostic build.

The same ship word (0), shot level (2), and player position (66, 480) were observed
in the PS2 pre-boss checkpoint and at both core starts in a separate arcade Stage 6
shortcut. Every sampled HP decrease in the two natural MAME logs and in the
compared PS2 logs was one point. The earlier core already falls at different rates,
and the timing difference comes from the spacing of sampled HP decreases. The next
comparison should log shot-to-core contacts and rose interceptions with the MAME
natural entry and fixed PS2 input before tuning burst size further.

The normal bl_mode ELF was byte-identical before and after the probe on the same
compiler, as was the exported kuro hook image. A direct retail-ELF kuro bake hit
the existing launcher preimage requirement and is not part of this comparison.
