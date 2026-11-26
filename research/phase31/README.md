# Stage 6 shot contacts

Phase 30 narrowed the difference in rose and bullet density. This probe measures
how often player projectiles reach the first core, the rose core, and the rose
parts. It records the native damage recipient after the engine follows parent
links. A contact is a call that reaches that target's hit-flash check. One shot
can produce several calls. HP lost is counted separately.

## Reproduce

Use the same rank lock (0x800000), shot level (2), stationary P1, and held shot
as Phase 30. Use a fresh MAME profile and the natural route through stages 1–5.

    mkdir -p runs/bl-stage6 runs/bl-cfg runs/bl-nvram
    OUTDIR=runs/bl-stage6 CONTACT_TAP="$PWD/research/phase31/bl_contacts.lua" \
      STAGE=7 BOSSTYPE=74 MAXFRAMES=130000 RANKLOCK=8388608 SHOTLOCK=2 \
      mame ibarablk -rompath ROMS -video none -sound none -nothrottle -nodrc \
      -cfg_directory runs/bl-cfg -nvram_directory runs/bl-nvram -nonvram_save \
      -noreadconfig -noplugins -skip_gameinfo -autoboot_delay 0 \
      -autoboot_script tools/stage_compare/bl_stage_log.lua

The MAME tap starts at stage frame 10,000. To shorten the run, first use the
same command with -drc, no CONTACT_TAP, and SAVE_STATE set to a new absolute path. The logger saves at stage frame
10,500. Start a second copy with -nodrc, CONTACT_TAP, RESUME_STATE set to that
path, and CONTACT_START=0. Its logged clock is relative to the restored state.
Use the interpreter for the trace because the SH-3 recompiler can bypass
memory taps.

Follow the [Phase 30 PCSX2 instructions](../phase30/README.md) and add
--define BL_ROSE_CONTACT_TEST at bake time. Keep other optional RAM probes
off. The hook runs only in Stage 6 and records type-74 core and type-79 rose
contacts. The buffer holds 24,000 rows below the native stack, with a dropped-record
counter. Replay modes 0 and 3 from the same pre-boss Practice checkpoint and repeat mode 3.

    python3 research/phase31/report_contacts.py --mame-run runs/bl-stage6 \
      baseline.p2s combined.p2s repeat.p2s

The core sampler marks the first positive and first zero HP at four-tick
intervals. The report includes a three-tick lead-in to cover the first interval.
Check that the trace accounts for every HP point. PCSX2 shows 430 HP in the
first sampled rose-core row. The contact trace catches the preceding 431-to-430
step as well. Compare damage per contact separately from elapsed time. MAME uses
display frame callbacks and PCSX2 uses native stage ticks.

## PCSX2 results

The two Phase 30 modes replayed from the same Stage 6 Practice checkpoint
at tick 10,902. These counts include repeated contacts by a single shot.

| Mode | Opening core ticks | Opening core contacts | Rose core ticks | Rose core contacts | Contacts with roses |
|---|---:|---:|---:|---:|---:|
| Baseline | 3,824 | 2,799 | 3,296 | 3,784 | 4,945 |
| Barrage and group size | 3,824 | 2,799 | 3,712 | 2,750 | 7,557 |

Both modes removed 359 opening-core HP and 431 rose-core HP through the
recorded shot calls. In the rose phase, 3,353 baseline contacts and 2,319
combined contacts arrived while hit flash was active. In both modes every
recorded zero-flash core contact removed one HP. Median spacing between HP
steps stayed at six ticks. The longer phase came from longer gaps between
successful hits, with the rate of core contacts dropping from 1.15 to 0.74 per
tick while contacts with roses increased from 1.50 to 2.04 per tick. The shot
types that caused the HP steps stayed almost identical (ship shot 317 to 316,
type-3 rocket 114 to 115).

The two combined runs produced identical contact event sequences across all
13,265 records and the same opening and rose core timings. The instrumentation
build is separate from the K55 hardware patcher. A first probe wrote records
into the EE stack as its buffer approached 12,000 entries. The current buffer
ends below 0x01FF0000 and reports overflow rather than wrapping.

## MAME instrumentation

The native damage function at 0x0C0A8E90 calls a parent-link helper when a
shot touches a linked part. The helper changes the live return address to
0x0C0A8EC8. The trace matches the saved return address at R14+8 against the
ordinary shot callers, with the corresponding shot pointer from the saved
R8 or R10. The first capture filtered on the live return address and missed
opening-core contacts from linked parts. A separate core-writes log records
HP changes with the native writer and live return address so missing damage
paths can be identified.

MAME's Lua binding may represent a high 64-bit access mask as a floating-point
number. Applying a bitwise operator to that value caused the tap to miss
high-lane accesses, including the rose core in slot 85. The trace extracts the
selected lane after a numeric shift when the binding supplies a float. This
also covers writes to odd slots that the first pass missed.

## Arcade replay timing

The pre-boss checkpoint came from a continuous Black Label run through
Stages 1–5. Applying held shot after the restore changed the subsequent
fight. Both the interpreter and recompiler measured 5,276 opening-core
frames and 4,264 rose-core frames in that control. Asserting held shot
before the restore reproduced all four Phase 30 reference values in the
recompiler: 5,492 opening-core frames, 3,272 rose-core frames, 4,149 type-79
activations and 1,986 type-14 activations in the rose interval. The logger
uses this input order when it resumes a checkpoint.

## Matched rose-phase contact comparison

A second checkpoint just before the rose form retained the reference input
history. The interpreter reproduced the 3,272-frame rose phase and recorded
all 431 core HP steps. The first four-frame sample sees 430 HP because the
first shot has already removed one point.

| Run | Rose core length | Core contacts | Contacts with roses | Mean HP-step gap | HP-step gaps over 12 |
|---|---:|---:|---:|---:|---:|
| MAME Black Label reference | 3,272 | 2,894 | 4,439 | 7.61 | 21 |
| PCSX2 baseline | 3,296 | 3,784 | 4,945 | 7.67 | 26 |
| PCSX2 combined | 3,712 | 2,750 | 7,557 | 8.64 | 51 |

All three traces recorded 431 one-HP losses. The median gap stayed at six.
The PCSX2 combined run had more gaps after the core was ready for another
hit. It also had 70% more contacts with roses than the arcade reference.
This accounts for the extra duration in this fixed-input test. It leaves
open how much of the change comes from rose placement, shot trajectories,
and the different shot types reaching the core. The benchmark logged type 0
for all arcade core hits. PCSX2 also landed 114 baseline and 115 combined
core hits from the type-3 rocket. This comparison made no gameplay changes
to the release patch.

Use --rose-only with the contact report for a capture started between the two
cores.
