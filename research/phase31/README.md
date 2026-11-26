# Stage 6 shot contacts

Phase 30 narrowed the difference in rose and bullet density. This probe measures
how often player projectiles reach the first core, the rose core, and the rose
parts. It records the native damage recipient after the engine follows parent
links. A contact is a call that reaches that target's hit-flash check. One shot
can produce several calls. HP lost is counted separately.

## Reproduce

Use the same rank lock (0x800000), shot level (2), stationary P1, and held shot
as Phase 30. Use a fresh MAME profile and the natural route through stages 1–5.

    mkdir -p runs/bl-stage6
    OUTDIR=runs/bl-stage6 CONTACT_TAP="$PWD/research/phase31/bl_contacts.lua" \
      STAGE=7 BOSSTYPE=74 MAXFRAMES=130000 RANKLOCK=8388608 SHOTLOCK=2 \
      mame ibarablk -rompath ROMS -video none -sound none -nothrottle -nodrc \
      -skip_gameinfo -autoboot_delay 0 -autoboot_script tools/stage_compare/bl_stage_log.lua

The MAME tap starts at stage frame 10,000. To shorten the run, first use the same command with -drc, no CONTACT_TAP,
and SAVE_STATE set to a new absolute path. The logger saves at stage frame
10,500. Start a second copy with -nodrc, CONTACT_TAP, RESUME_STATE set to that
path, and CONTACT_START=0. Its logged clock is relative to the restored state.
Use the interpreter for the trace because the SH-3 recompiler can bypass
memory taps.

Follow the [Phase 30 PCSX2 instructions](../phase30/README.md) and add
--define BL_ROSE_CONTACT_TEST at bake time. Keep other optional RAM probes
off. The hook runs only in Stage 6 and records type-74 core and type-79 rose
contacts. The buffer holds 24,000 rows below the native stack, with a dropped-record counter. Replay
modes 0 and 3 from the same pre-boss Practice checkpoint and repeat mode 3.

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
