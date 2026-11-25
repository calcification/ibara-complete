# Arrange stock and stage-comparison follow-up

Baseline K45 at 6b4ce617. Runs used PCSX2 2.8.2 and MAME 0.276. Slowdown remains paused.

## Arrange CONFIG

The Address column is relative to the retail boot ELF with GP 0x0033FCF0. In PCSX2, two Arrange
starts from the same Mode Select savestate used raw Arcade values [0, 0, 0, 0, 0, 0] and
[3, 3, 3, 3, 1, 1], in table order. At ticks 937 and 938 the mode was Arrange, the values remained
in RAM, and the following gameplay behavior was observed.

| Arcade field | Address | Arrange evidence |
|---|---|---|
| DIFFICULTY 1 | 0x00338BF4 | Starting stored rank 0xFFFFFF in both runs. The Arrange branch at 0x0012CC14–0x0012CC90 uses fixed starting rank and bypasses the Arcade lookup tables. |
| DIFFICULTY 2 | 0x00338BF8 | Same boot check. Direct reads of this field feed the skipped Arcade lookup or configuration and replay state. |
| PLAYER STOCK | 0x00338C00 | Two spare lives in both runs. The Arrange branch at 0x0012D8E8 avoids the Arcade byte. |
| BOMB STOCK | 0x00338C04 | Starting bomb counter changed from 0 to 1. The start/refill logic reads this byte at 0x0012D5A0. The refill at 0x0012D7D0 branches on Arrange before the Arcade read at 0x0012D7FC. |
| EXTEND | 0x00338BFC | The Arcade lookup at 0x0013E290 reads the setting, but Arrange sets its own initial extend at 10,000,000 (0x0012D930) and a fixed 10,000,000 interval (0x0013AC54). |
| CONTINUE | 0x00338BEC | The native countdown/continue paths at 0x0012C5B4, 0x0012C734, and 0x0012C934 branch on Arrange. No forced game-over in this run. |

Two opt-in PCSX2 prototypes implement **PLAYER STOCK only**. Enable one profile on the original
disc, CRC 420C7FAB, then open Arrange CONFIG. Neither profile writes a new setting to the memory card.

    python3 research/phase26/build_arrange_stock_probe.py SLPM_663.01 --mode rows --output /path/to/PCSX2/cheats
    python3 research/phase26/build_arrange_stock_probe.py SLPM_663.01 --mode copy --output /path/to/PCSX2/cheats

- **A, PLAYER STOCK.** Circle cycles 0–5 spare lives from the retail default of 2. PCSX2 started
  with 3 after one press and a return through the native Exit row.
- **B, COPY STOCK.** Circle snapshots the current Arcade setting. PCSX2 copied 4, then started
  Arrange with 4 after Arcade was changed to 1. Arcade still held 1.
- Both options added a single row before Exit. Start with a fresh emulator boot to reset the
  prototype value. Turn cheats off for normal play or when booting the production K45 patch.

## Logger and damage measurements

The build and extractor now use versioned rolling buffers for enemy spawns, bullets, and core
samples. Each row carries the native stage byte and tick. Exports remain chronological and report
loss of early records. The host stress test ran the real logger across two simulated stages.
It retained 2,600 / 7,000 / 8,000 records after overwriting 89,560 / 8,360 / 38,080 respectively.
A separate MIPS build verified the 16,000-record alternate core layout. A PCSX2 Stage 6
Practice checkpoint resumed to native tick about 17,500. Its exported save retained the latest
2,600 spawns and 7,000 bullets after overwriting 3,435 spawns and 127 bullets. All retained
rows were in chronological order and carried native stage byte 7. It also retained 1,438
boss samples. See the
[runner documentation](../../tools/stage_compare/README.md).

The repeat-trial report records HP and observed elapsed frames for one core subtype. The six-stage
post-spark damage audit still needs matched trials. Phase 15's Stage 2 PS2 core escaped with positive HP,
which is why a last sampled frame alone is insufficient for timing a kill. Stage 4 also needs a separate
HP source for its boss. The historical results remain in [Phase 15](../phase15/README.md) and
[Phase 25](../phase25/README.md).

## Stage 6 rose form

Phase 25 measured 6,876 frames for the Black Label rose core and 4,956 for the Noir core.
The first form and rose defense need their own timing measurements.

A Stage 6 shortcut in MAME captured 2,914 Black Label type-79 writes. The constructor at
0x0C0A8090 wrote the primary part at 0x0C0A8108 and the linked part at 0x0C0A818A. Counting
the 1,776 primary writes separately gave 310 burst frames. In 276 of the 309 gaps between
bursts, the next burst came 11 MAME frame callbacks later. This was a diagnostic start, with
stage script and stage record set directly after starting Stage 1. Use natural entry to measure
core lifetime and the full-run burst distribution.

- Black Label's rose helper 0x0C0A2900 has three constructor call sites, 0x0C0A2C30,
  0x0C0A2E96, and 0x0C0A3152. These paths call the timer at 0x0C0BC1B0 first.
  Its increment/reset runs on the part's flag 0x100 and uses a stage- and difficulty-adjusted
  rank. The timer arguments at these sites are (scale 20, base 10), (10, 10), and (10, 10).
- The analogous PS2 constructor 0x00163140 has corresponding sites 0x00178F44,
  0x001790DC, and 0x00179190. The timer at 0x00122120 takes the same arguments in these
  paths, but uses the direct stored rank there. That isolates a candidate cadence difference
  that can be tested at these three callers without changing enemies that share the timer.
- The same Black Label paths call the bullet emitter at 0x0C0BA970 after each rose attempt,
  using the pattern at 0x0C189C9C. Its type field writer at 0x0C0BAA42 appears in the type-14
  trace. The second shortcut run recorded 1,523 type-14 writes through that pattern
  between stage-relative frames 17,670 and 21,873. The corresponding PS2 rose loops return
  to the next slot after the rose constructor.
  The type-14 trace also sees other attacks, so group by caller before measuring the extra
  barrage. The barrage port is still pending.

For an A/B timer bake, pass --define BL_ROSE_TIMER_TEST=3 to the separate stage-6 logger builder.
This replaces the rank input only at the three rose calls. Use the arcade difficulty byte from
the target run in place of 3. The value 3 was seen in an early arcade RAM snapshot. Verify it
again in the matched stage-6 runs. The bake verifies the three retail call words, and host tests
cover the timer's enable flag, cadence, reset, and rank clamp. The production K45 build has no timer probe. Compare the core's first sampled HP to
its first sampled zero HP on the same scripted input and checkpoint.

PCSX2 Stage 6 Practice trials used the same pre-boss checkpoint at native tick 10,455.
All three finished the phase. The logger locked shot level 2 and stored rank 0x800000. Durations
are from the first positive HP sample to the first zero HP sample for the indicated core.

| PS2 timer | First core ticks | Rose core ticks | Type-79 activations | Type-79 activations per active tick |
|---|---:|---:|---:|---:|
| Retail, run 1 | 4,652 | 3,320 | 3,029 | 0.95 |
| Retail, run 2 | 4,056 | 3,140 | 2,823 | 0.95 |
| Adjusted, one run | 3,956 | 2,796 | 2,640 | 1.00 |

The activation denominator spans the first through last logged type-79 frame. Controller
timing at restore was host-driven, and first-form timing differed before roses appeared.
The one adjusted run had a higher spawn rate and a shorter rose phase than either baseline
run. The timer alone has not closed the measured lifetime gap. Compare synchronized trials
with the barrage in place before taking either change into the hardware patch.

Use the type-write tracer to resolve the constructor caller or investigate the barrage. Remove
QUICK_S6 for natural entry and allow enough frames to reach the rose form.

    OUT=roses.txt QUICK_S6=1 STAGE=7 TYPE=79 MAXF=34000 mame ibarablk -rompath ROMS -nodrc \
      -video none -sound none -nothrottle -autoboot_script research/phase25/bl_spawn_pc.lua
    OUT=barrage.txt QUICK_S6=1 POOL=bullets STAGE=7 TYPE=14 MAXF=34000 mame ibarablk -rompath ROMS -nodrc \
      -video none -sound none -nothrottle -autoboot_script research/phase25/bl_spawn_pc.lua

## Pod shot counts

The existing frame-end sampler can now report the exposure per weapon and stage with EXPOSURE=1.
In MAME 0.276 five-way had 952 sampled activations in 1,000 Stage 2 frames, homing 63 in
1,000 Stage 2 frames, and napalm 52 in 1,000 frames spanning the end of Stage 1. Gatling
ran twice, with 1,000 frames each in Stages 1 and 2. Future paired trials should match the
stage and the number of frames measured. The raw takeaways from Phase 16 remain useful,
but its per-window counts cannot resolve same-frame slot reuse. An attempted CPU-write
counter produced no allocation events and did not resolve that ambiguity.

## K45 validation

The full Black Label zip worked through the Python patcher. The patched ISO was 3,932,848,128
bytes. PCSX2 confirmed Noir GAME START entered the P1 selector directly (H2) and Arcade NORMAL,
HARDER, and EXTENDED each entered Stage 1 (H3). Noir launched after ship confirmation. That
check did not measure the select theme's loop length, volume, or transition (H4). The probes
in this follow-up produce their own local test files. Use the existing K45 patcher for the
[original-PS2 checklist](../../docs/HANDOFF_2026-11-25.md#hardware-test-list-original-ps2-patcher--clean-iso----bl-rom-with-u23u24-in-the-zip).
No tests in this follow-up were run on original hardware.
