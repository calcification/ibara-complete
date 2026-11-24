# Retail Arcade slowdown prototype

The integrated [test patcher](../../patcher/README.md) adds **Arcade Mode → Config → Slowdown**.
It starts OFF with both retail gameplay branches in place. In PCSX2 2.8.2, the repatched
disc produced 60 gameplay ticks in 60 Arcade Practice refreshes with the switch OFF and
L2+R2 held. With the switch ON, L2+R2 changed the measured cadence from 60/60 to 30/60
and back to 60/60 on the next press. A held chord fired once. Noir kept its shorter
Config menu and restored the Arcade setting on exit. Original PS2 validation is pending.


S01 tests the gameplay gate in the Japanese retail PS2 executable (SLPM-66301, PCSX2 CRC
`420C7FAB`). When armed in live Arcade play, it holds every other core update. The fixed cadence is
a diagnostic for a future arcade timing model. Arcade Normal and Arcade Practice are eligible.
The policy uses the native pause and transition guards and excludes attract and Arrange.

## Build and inspect

```sh
python3 research/phase22/build_slowdown.py "Ibara (Japan).iso" --output /path/to/pcsx2/cheats
```

The builder uses the repository's MIPS n32 cross toolchain. It checks the retail ELF hash and both
hook preimages. Use the generated S01 profile alone on a cold boot in PCSX2 with a disposable card.
The enable word starts at zero. From the repository root, use PINE in a live Arcade stage to compare
forced holds against the control run.

```sh
python3 scripts/pcsx2_pine.py read32 000C0000 000C0004 000C0008 000C000C 00338CDC 00338EA0
PYTHONPATH=scripts python3 -c 'from pcsx2_pine import Pine; p = Pine(); p.write(0x000C0004, 1); p.close()'
PYTHONPATH=scripts python3 -c 'from pcsx2_pine import Pine; p = Pine(); p.write(0x000C0004, 0); p.close()'
```

| EE address | Meaning |
|---|---|
| `0x000C0000` | Probe signature `0x31574453` |
| `0x000C0004` | Enable word, set to 1 for alternating holds |
| `0x000C0008` | Cumulative held updates |
| `0x000C000C` | Hold flag for the current outer iteration |
| `0x000C0010`, `0x000C0014` | Deferred press and release halfwords for P1 and P2 |
| `0x00338CDC`, `0x00338EA0` | Native outer-loop count and stage gameplay tick |

The probe replaces the branch at `0x0012E1E4` and keeps the retail simulation and draw destinations.
The rank gate at `0x0012E47C` holds the passive rank decrement on probe-held iterations. Pad polling
continues through the outer loop. The probe carries shot and bomb edges to the next gameplay tick.
Arcade's bomb routine checks the release field at player offset `0x252`; a short tap can otherwise
lose its release on a held update.

## PCSX2 verification

In retail Arcade Stage 1 on PCSX2 2.8.2, a frame-advance control ran six gameplay updates in six
VSyncs. Restoring the same save state and enabling S01 produced six gameplay updates in twelve
VSyncs. Ship position and rank were steady on each held VSync and matched the control at each
gameplay tick. In a separate run with three bombs set as a test fixture, a controller release on a
held VSync stayed queued until the next gameplay tick. The game consumed one bomb, and the probe
cleared the deferred release. Native Pause held both the stage tick and the probe counter steady.
Disabling the probe after a held VSync restored one gameplay update per refresh immediately.
Arcade timing calibration remains pending.

### Workload capture

Build S01 with `--capture` to add a research recorder. It starts disabled and needs its own
PCSX2 profile on a cold boot. Keep the slowdown control at zero for the stock capture.

```sh
python3 research/phase22/build_slowdown.py 'Ibara (Japan).iso' --capture --output /path/to/pcsx2/cheats
python3 research/phase22/workload_capture.py arm
# Play the window to sample, then pause PCSX2.
python3 research/phase22/workload_capture.py export capture.csv
```

The recorder saves up to 2,048 consecutive eligible outer iterations at `0x000D0000`. Each row
is taken before the gameplay update and includes the current tick, rank, P1 position and bomb
state, active enemy and item slots, hostile bullet slots, and Rose Pods. The holding flag tells
whether the probe skipped the update. Keep recordings within one live scene and validate the
outer-loop increments, since pause and transitions are omitted. These counts are telemetry
candidates. They do not model the original board's drawing workload by themselves.

For repeatable Stage 6 Arcade Practice runs, pause once Teresa's flying form appears and save a
checkpoint with at least one full bomb. Arm with `--bomb-delay 14 --charge-ticks 138` from that
paused checkpoint and resume without gameplay input. The recorder schedules a P1 bomb hold and
release at fixed gameplay ticks. Restore the checkpoint before changing one test condition, such
as position, rank, or forced cadence. Wait for PCSX2 to finish loading the state before arming
again. Check the input edge and the fall in bomb stock in the CSV. With the current capture
profile, `--shot-ticks 360` also holds shot from the start of the charge through 360 gameplay
ticks after launch. It records a separate shot release edge.

#### Stage 6 replay check

From a single paused flying-form checkpoint, the bomb released at gameplay tick 2300 in
both stock runs and the forced run. The stock runs advanced the next 600 gameplay ticks in
600 refreshes. The forced run advanced them in 1,200 refreshes with 600 holds. For the 601
advancing samples starting at the release, the stock repeat and the forced run exactly matched
the first stock run's player coordinates, rank, input edges, bomb stock and object counts.
Resume-to-pause VSync totals also matched the outer-loop deltas in all runs.

An otherwise identical left-side stock run used a higher starting rank. Peaks over the 600
gameplay ticks after the release changed as follows. Counts are maxima per pool and can occur
on different ticks.

| Starting inverted rank | Hostile bullets | Active enemy slots | Rose Pods | Active items |
|---|---:|---:|---:|---:|
| `0x600000` | 11 | 83 | 36 | 31 |
| `0x200000` | 41 | 133 | 63 | 59 |

A second checkpoint compared a Bond Type C Hadou launched beside each side of Teresa. Both
started at inverted rank `0x600000` and released at tick 2327. The rotated display maps
the game's internal Y coordinate to the horizontal screen axis. At internal X 48, Y 435
and Y 555 put the Hadou visibly on the left and right of Teresa, respectively. Both stock
runs advanced one gameplay tick per refresh.

| Launch position | Hostile bullets | Active enemy slots | Rose Pods | Active items |
|---|---:|---:|---:|---:|
| Left | 72 | 192 | 64 | 55 |
| Right | 20 | 130 | 36 | 29 |

This validates the capture and repeated input at one native encounter. These are controlled
PS2 routes with seeded rank and bomb stock, and the flower phase was shortened to reach the
checkpoint. The right lane populated fewer object slots in this same-ship PS2 test. Y.S.333's
right-lane Dyne run had the larger number of repeated video fields. The DYNE firing sequence,
hidden arcade rank and draw cost still need to be accounted for before using these routes for
release calibration.

To pass the same 600-tick window to the timing scorer, extract it from each workload CSV.
The conversion takes the first pre-update sample at the requested tick and checks continuity
through the end of the window.

```sh
python3 research/phase22/workload_capture.py timing stock-capture.csv stock.csv --window stage6-hadou --start-tick 2300 --ticks 600
python3 research/phase22/workload_capture.py timing forced-capture.csv forced.csv --window stage6-hadou --start-tick 2300 --ticks 600
python3 research/phase22/score_slowdown.py stock.csv forced.csv --reference-kind diagnostic
```

This diagnostic correctly reports one extra 600-hold event in the forced run, starting on
refresh 1. The stock capture has zero holds in that window.

#### Dyne and graphics workload

With one checkpoint, the same right-side position and inverted rank `0x600000`, changing the
P1 ship mechanics word at `0x0044C384` from Bond Type C (`2`) to Dyne Type B (`5`) barely
changed the first Hadou-only run. The first logged difference after launch appeared at tick
offset 540 when Dyne had one additional active enemy slot. Both runs peaked at 39 Rose Pods
and 17 hostile bullet slots. With Dyne at inverted rank `0x200000`, the same input reached
86 pods and 76 hostile bullet slots. The ship switch tests the retail mechanics tables in
one slot. The original Y.S.333 run uses P2 and has a different firing and movement sequence.

For a short sample of actual graphics commands, use PCSX2's `GSDumpSingleFrame` hotkey.
Set GS dump compression to **Uncompressed** or **XZ**, and keep the dump in a local
temporary folder. Run the parser on that dump.

```sh
python3 research/phase22/gs_workload.py frame.gs
```

The parser counts GIF transfer and image-upload quadwords and assembles GS primitives. The
filled-area field sums submitted sprite rectangle and triangle areas before clipping or
alpha tests. Use the interior refreshes of each dump to avoid the capture boundaries.
Use these as PS2 rendering measurements. Hardware timing still requires CV1000 calibration.
[PCSX2 dump format](https://github.com/PCSX2/pcsx2/blob/v2.8.2/pcsx2/GS/GSDump.cpp) ·
[GIF registers](https://github.com/PCSX2/pcsx2/blob/v2.8.2/pcsx2/GS/GSRegs.h)

In a fresh checkpoint used for the capture comparison, neither Dyne rank had hittable
hostile bullets during the first 600 ticks after launch. At about 418 gameplay ticks after
launch, Dyne at `0x600000` submitted 871–889 primitives per refresh. At `0x200000` it
submitted 1,288–1,293. The submitted area rose from 1.01–1.02 million to about 1.15 million
pixel units. The ranks were compared within the same checkpoint. The earlier object-pool
run used a different checkpoint, which had different enemy and item sequences.

At about 288 gameplay ticks after the first Hadou launch, the same-rank Bond-left and
Dyne-right routes both held shot through the charge and launch. Bond's two interior GS
refreshes submitted 1,067–1,110 primitives and roughly 1.26 million pixel units of area.
Dyne submitted 943–947 primitives and 1.15–1.17 million pixel units. At the corresponding
approximate elapsed gameplay time, KMT's superplay still precedes the first sustained
repeat run, while Y.S.333's sits well inside it. A single GS primitive-count or area
threshold fitted to the equal-rank PS2 routes gives the wrong ordering at this point.
The ship and lane match the broad arcade routes. The original rank and shot timing
remain unknown.

A second comparison kept Bond at `0x600000` and raised Dyne to `0x200000`. This reversed
the primitive counts at about 288 gameplay ticks after launch, with Bond at 980 and Dyne
at 1,211–1,214. A single increasing threshold still fails across the sampled windows.
During Dyne's earlier, already slow reference window (about tick 218), the PS2 route
submitted 925–926 primitives and 1.198–1.199 million pixel units. During Bond's later,
still fast reference window (about tick 288), the PS2 route submitted 980 primitives
and 1.203 million pixel units. Here both graphics measures are lower for the slow
reference segment. These are approximate landmarks in reconstructed routes with
seeded rank and scripted shot input.

The CV1000 timing implementation in ibara360 accounts for draw dimensions, VRAM
accesses, and waits incurred by the arcade CPU. Those terms give the next comparison
a physical basis beyond visible density or PS2 graphics totals.
[Arcade blitter timing](https://github.com/PaulAtreides67/ibara360/blob/main/runtime/blitter.c#L458) ·
[CPU timing model](https://github.com/PaulAtreides67/ibara360/blob/main/runtime/pcb.c#L526)

#### Original CV1000 program in MAME

The Stage 6 fixture uses the original Ibara set, U4 CRC `d5fb6657`, in MAME 0.276. At the
Normal script's first VBlank it redirects the script pointer `0x0C2859A0` from `0x0C1EEEC6`
to Garden's native entry at `0x0C1EEEEA`. It supplies the preceding stage number so the
native command loads Garden and advances to scene 7. Setting the scene byte alone left
Stage 1's terrain loaded in testing. The fixture follows the same stage-entry method
documented in ibara360 and uses that project's enemy timer and player-record findings.
[Normal stage entry](https://github.com/PaulAtreides67/ibara360/blob/main/host/xsdk/ibara360/source/main.c#L12532) ·
[Original Teresa timers](https://github.com/PaulAtreides67/ibara360/blob/main/host/xsdk/ibara360/source/bossclock.c#L858)

Run from the repository root with the original ROM set. Use fresh MAME configuration
and NVRAM directories and a fresh output filename for each run.

```sh
IBARA_SIDE=1 IBARA_RANK=600000 IBARA_TRACE=bond.csv \
  mame ibara -rompath /path/to/roms -cfg_directory /path/to/fresh-cfg \
  -nvram_directory /path/to/fresh-nvram \
  -nodrc -video none -sound none -nothrottle -skip_gameinfo -autoboot_delay 0 \
  -autoboot_script research/phase22/cv1000_stage6.lua
```

Use `IBARA_SIDE=2 IBARA_RANK=200000 IBARA_TRACE=dyne.csv` for the second run. The fixture
shortens the midboss and flower timers, leaves the game to spawn the flying form
(`0x4A`, subtype `0x02`), and seeds ship type, rank, position and power. It then uses
the native shot and bomb inputs. In both runs the flying form appeared at gameplay tick
12662 and the bomb release input was sent at tick 12814. The rendered game showed
Bond's left-lane and Dyne's right-lane Hadou launches.

The tracer records the submitted list at `0x18000004` and the EP1C12 device's modeled
blitter duration per job. The draw totals include clipping, blended draws, texture
upload bytes and VRAM access estimates. The two runs each advanced **600 gameplay ticks
in 600 refreshes** after release, with one blitter submission per refresh. A second
Bond capture matched all 793 rows of the first export across the common columns.

| Route | Median modeled blitter time | Peak | Peak with list-transfer allowance |
|---|---:|---:|---:|
| Bond C at `0x600000` | 7.902 ms | 10.034 ms | 11.783 ms |
| Dyne B at `0x200000` | 7.923 ms | 10.606 ms | 12.091 ms |

The rightmost column adds 300 SH-3 cycles per 64-byte list block at 102.4 MHz, as a
ranking test based on ibara360's bus allowance. A 60.024 Hz refresh is about 16.66 ms.
The sum is a diagnostic, since CPU work and blits can overlap and the arcade CPU
also incurs cache and memory stalls.
[CV1000 driver](https://github.com/mamedev/mame/blob/mame0276/src/mame/cave/cv1k.cpp) ·
[ibara360 bus timing](https://github.com/PaulAtreides67/ibara360/blob/main/runtime/blitter.c#L848)

Around 283–293 elapsed gameplay ticks after launch, KMT's DVD window precedes its first
sustained repeats and Y.S.333's is already inside its long repeat run. The MAME fixtures'
median blit time was 8.624 ms for Bond and 7.269 ms for Dyne. With the list allowance
the medians were 10.183 and 8.614 ms, respectively. In Bond's later 446–461 window,
roughly inside the second visible repeat burst, the median modeled blit fell to
7.787 ms even as the list grew to 45.1 KB from 33.9 KB. These are approximate DVD
landmarks and seeded arcade routes. The comparison rules out using these two
timing totals alone as a threshold for the sampled routes. The original rank, options,
shot sequence, and SH-3 time available before the next refresh are further variables
to account for before scoring the 80% target.

#### Original SH-3 timing

The same fixture samples the original game's TMU1 counters once per refresh. The
interval between the game's video IRQ timestamps alternates between 16 and 17 timer
ticks in MAME 0.276, or about 1 ms per tick at 60.024 Hz. `profile_tmu` is the game's
last profiling checkpoint and `irq_tmu` is the most recent video IRQ timestamp. On
an uninterrupted iteration the game updates its logic counter, prepares the list,
and records its last checkpoint after publication. Use `profile_tmu - irq_tmu` for
the elapsed work through this checkpoint and `tmu - profile_tmu` for time remaining
at the refresh boundary.
The latter is a measure of slack, including the synchronization wait and small
loop overhead. Keep the original refresh index when gameplay ticks repeat, and
read the phase durations only on completed iterations. The `pre` interval spans
the synchronization wait plus setup work. The `sim_a` through `sim_c` intervals
cover gameplay work before the logic counter increment at `0x0C05ADA4`.
[TMU1 setup and ISR](https://github.com/PaulAtreides67/ibara360/blob/main/gen/ibara_drc/recomp_00.c#L869) ·
[Video IRQ timestamps](https://github.com/PaulAtreides67/ibara360/blob/main/gen/ibara_drc/recomp_02.c#L3084) ·
[Gameplay timing checkpoints](https://github.com/PaulAtreides67/ibara360/blob/main/gen/ibara_drc/recomp_05.c#L3781)

The timer capture preserved all 793 workload rows on each route. Median intervals
in MAME 0.276 are shown below in approximately 1 ms timer ticks.

| Route and gameplay ticks after release | Video IRQ to last checkpoint | Last checkpoint to refresh | Modeled blitter duration |
|---|---:|---:|---:|
| Bond, 283–293, DVD still fast | 10 | 7 | 8.624 ms |
| Dyne, 283–293, DVD already slow | 8 | 9 | 7.269 ms |
| Bond, 446–461, later DVD slowdown | 11 | 6 | 7.787 ms |

The original program publishes a completed list at `0x0C283C94`. The video IRQ
routine submits it only if the FPGA ready bit is set. The main loop can wait for
the published list to be consumed. This lets a slow list cost an additional
refresh and lets CPU work and blitting overlap. The measured CPU and blitter
times therefore need their ordering relative to the IRQ when testing a deadline
model. The interpreter CPU interval alone ranks the Dyne window below the fast
Bond window in these seeded routes.
[List publication](https://github.com/PaulAtreides67/ibara360/blob/main/gen/ibara_drc/recomp_02.c#L3299) ·
[Ready check](https://github.com/PaulAtreides67/ibara360/blob/main/gen/ibara_drc/recomp_02.c#L2850) ·
[Main-loop wait](https://github.com/PaulAtreides67/ibara360/blob/main/gen/ibara_drc/recomp_02.c#L1292)

Set `IBARA_EVENTS=bond-events.csv` alongside the original command in MAME 0.276
with `-nodrc` to record scheduler timestamps at the IRQ checkpoint, CPU setup,
gameplay update, list publication, and submit. Join by `outer`. The submit
event belongs to the iteration that prepared the list, immediately before the
next IRQ counter increment. In Bond's 284–289 window, the median IRQ-to-list time
was 10.10 ms and the list waited 6.48 ms before submit. In Dyne's window at those
same ticks, the medians were 7.05 ms and 9.53 ms. At Bond's later 451–455 window
they were 10.24 ms and 6.34 ms. All sampled lists made the next IRQ, including
those in the slower DVD windows. The event taps preserved the original gameplay
and draw-list rows and occasionally moved a coarse timer reading by one tick.

For a MAME 0.289 interpreter versus dynamic-recompiler comparison, run the same
two routes with `IBARA_CPU_ONLY=1`, once with `-nodrc` and once with `-drc`. This
mode disables the blitter tap and records `-1` for the blitter columns. The 0.289
SH7709S core adds experimental instruction-cache and SDRAM penalties in its
recompiler, so its results are emulator timing estimates.
[SH7709S timing in MAME 0.289](https://github.com/mamedev/mame/blob/mame0289/src/devices/cpu/sh/sh7709s.cpp#L348)

Both 0.289 modes completed **600 gameplay updates in 600 refreshes** after
release on both routes. The 0.289 interpreter matched the 0.276 medians shown
above, with individual timer readings occasionally differing by a tick.
With the recompiler, the median video IRQ to checkpoint interval
increased by 3 ticks over the paired samples where the tracked rank, bombs,
boss age, and logic tick agreed. Those samples cover Bond's first 29 updates
after release and Dyne's charge lead-in at −151 through −114. Both routes'
rank counters diverged between modes before the DVD comparison windows, so
the later timing differences include gameplay differences.

| Route and gameplay ticks after release | Interpreter to checkpoint | Recompiler to checkpoint | Recompiler slack |
|---|---:|---:|---:|
| Bond, 283–293 | 10 | 14 | 3 |
| Dyne, 283–293 | 8 | 14 | 3 |
| Bond, 446–461 | 11 | 13 | 4 |

The cache model brings the CPU closer to the refresh deadline. The slow DVD
window for Dyne ends up with the same median CPU time and slack as the fast
Bond comparison. The later slow Bond window has more slack than the earlier
fast window. These routes provide a measured CPU timing range, and the
80% PS2 event-accuracy target still needs a validated arcade reference with
matched gameplay state.

## MAME as the working arcade reference

Use the supplied base-game `ibara` set (U4 CRC `d5fb6657`, 2006-03-07 revision) for the first Arcade
comparisons. `ibarao` is the earlier 2005-03-22 revision and has a different program CRC, `8e6c155d`.
For Black Label, use `ibarablk` (U4 CRC `ee1f1f77`) when starting separate gameplay measurements.
Both use MAME's CV1000-B machine configuration, which runs at the 60.024 Hz measured on the
Ibara board. The driver marks both games' timing imperfect. [MAME 0.289 CV1000 driver](https://github.com/mamedev/mame/blob/mame0289/src/mame/cave/cv1k.cpp#L540)

Buffi's October 2026 bench ran the same stress program on a physical Ibara PCB and in MAME.
The modeled blitter was within about 1% in the author's assessment, and the mixed game-like
tests were close. MAME ran one CPU-heavy logic ramp 42% faster, while its memory test was
about 27% slower. Those are benchmark workloads. The search found no matched in-game PCB
and current-MAME timing traces for either Ibara revision family. MAME added SH-3 memory, cache,
and NAND timing changes after 0.289, so pin the build as well as the ROM in every comparison.
[PCB benchmark](https://buffis.com/arcade/benchmarking-cv1000-pcb-vs-mame-and-mister/) ·
[Post-0.289 memory and NAND timing](https://github.com/mamedev/mame/pull/15685) ·
[Post-0.289 cache timing](https://github.com/mamedev/mame/pull/16063)

I ran the author's benchmark v1 autorun ZIP in a separate ROM folder in stock MAME 0.289
with `-drc` and `-nonvram_save`. The same two mixed workloads were within 0.5% of the posted PCB
results. The CPU workloads give a wider range for that release.

| Benchmark v1 | Ibara PCB | MAME 0.289 | Difference |
|---|---:|---:|---:|
| Mixed game ramp, objects at 60 Hz | 1,694 | 1,701 | +0.4% |
| Mixed game frame throughput | 171.3 FPS | 171.8 FPS | +0.3% |
| CPU logic ramp, objects at 60 Hz | 1,503 | 2,319 | +54.3% |
| CPU memory throughput | 20.1 MB/s | 16.3 MB/s | −18.9% |

The [published PCB result screen](https://buffis.com/wp-content/uploads/2026/10/bench_pcb.png)
has the comparison values. The stock 0.289 results above and the same author's October MAME
results measure different builds. The post-release CI artifact download was unavailable here.

### Base Ibara Stage 1 reference

Run from the repository root with a clean MAME configuration and NVRAM directory. The fixture
coins in, starts P1, and captures 300 refresh intervals beginning at the first live hostile shot
in Stage 1. It requests left, right, and shot on fixed refreshes and reads game state without
writing it. The CSV records the input request mask (left 1, right 2, shot 4), native 16.16
coordinates, score, rank, bomb stock, and live hostile bullet records.

```sh
IBARA_TRACE=stage1.csv mame ibara -noreadconfig -drc -noplugins \
  -rompath /path/to/roms -cfg_directory /path/to/fresh-cfg \
  -nvram_directory /path/to/fresh-nvram -nonvram_save \
  -video none -sound none -nothrottle -frameskip 0 -skip_gameinfo \
  -autoboot_delay 0 -autoboot_script research/phase22/cv1000_stage1.lua
```

Two fresh runs in MAME 0.289 matched byte for byte and matched two fresh runs in 0.276. All
four captured 300 gameplay updates in 300 refresh intervals, a score of 3,010 at the end,
and up to nine live hostile bullets. The common CSV SHA-256 was
`812bf544432be6ac88ca7e417b6b01b9ce2ef6b600345fbc128b933f8d861d5e`.
`score_slowdown.py --reference-kind diagnostic` reported zero extra events and no cadence
divergence. Use this as the quiet Arcade control.

### Base Ibara Stage 6 slowdown reference

Use the original Stage 6 fixture command above with MAME 0.289 and `-drc` in place of `-nodrc`.
Set `IBARA_CPU_ONLY=1 IBARA_RANK=0 IBARA_POST_RELEASE=1800` and set `IBARA_CADENCE` to a fresh
CSV path for the scorer. The fixture seeds player position, ship type and power, and anchors
the trace at the refresh when it requests Hadou release during Teresa's flying form. The zero
inverted rank is the hardest rank. No MAME clock or speed slider adjustment was used.

| Route | Updates after release | Refresh intervals | Held refreshes | First hold |
|---|---:|---:|---:|---:|
| Bond C, left lane | 1,800 | 2,000 | 200 | 162 |
| Dyne B, right lane | 1,800 | 1,804 | 4 | 159 |

Bond's first 600 updates include all 200 holds and six events under the existing scorer's
grouping. A second fresh Bond run matched the entire timing sequence and the recorded gameplay
state fields. The raw CPU profiling timers differed in some rows. The scorer found six matches
with zero misses or extras. The 1,800-update cadence CSV SHA-256 is
`3c2f0454430aca2031f5c552ba1a68819a74083270e047be9a8af59138011ec3`. For a PCB accuracy
score, compare onset and held-refresh count on the same attack with matched inputs, rank, and ship.

### Replay the MAME timing in PCSX2

With `IBARA_POST_RELEASE=600`, the Bond fixture exports a window that fits the existing S01
cadence buffer. Use it with the `--capture` build in PCSX2, paused in Arcade Practice Stage 6
at Teresa's flying form. The test used Bond C at x=48 and y=435, hardest rank, three full bombs,
and invulnerability refreshed through PINE.

```sh
python3 research/phase22/workload_capture.py arm --bomb-delay 14 --charge-ticks 138 \
  --shot-ticks 360 --cadence bond-cadence.csv
```

In PCSX2 2.8.2 the control run advanced 600 updates in 600 refresh intervals. Starting from
the same checkpoint, S01 replay advanced 600 updates in 800 intervals and placed all 200 holds
on the MAME refreshes. All 814 compared advancing samples across the charge and attack matched
the control's player position, rank, inputs, bomb stock, and object counts. This verifies the
PS2 game can follow a recorded MAME schedule. Deriving the holds during regular play is the
remaining implementation work.

### Fit an automatic rule to the MAME runs

The max-rank MAME routes contain six Bond slowdown events and three Dyne events over the first
600 gameplay updates. I recorded corresponding PS2 fixtures in PCSX2 and kept a 300-update Arcade
Normal Stage 1 capture as a quiet check. The PS2 Stage 1 capture advanced every refresh.

The existing threshold fitter missed all events when fitted on one Stage 6 route and tested on
the other. A second family averages object counts and their changes over eight updates and builds
up a fractional hold budget from that workload. It can insert at most one extra refresh per
update. With the launch-aligned fixtures, this rule also matched zero held-out events on either
route. Both fitted rules in this budget test produced zero holds in the Stage 1 control.

```sh
python3 research/phase22/assess_budget.py \
  --case stage6-bond bond-cadence.csv bond-stock.csv \
  --case stage6-dyne dyne-cadence.csv dyne-stock.csv \
  --quiet stage1-stock.csv
```

Set `IBARA_OBJECTS` to a fresh CSV path in the Stage 6 MAME command to log active enemy, Rose
Pod, and hostile bullet slots once per gameplay tick, including the lead-in to release. In the
max-rank routes, the first Rose Pod appeared 21 ticks before Hadou release for Bond and 30 ticks
before release for Dyne. The first Rose Pod in both PS2 captures appeared 103 ticks after their
release. MAME already had 33 pods on both routes at the launch anchor, where PS2 had zero.
Matching the launch alone therefore compares different phases of the attack.

I moved the full shot and bomb sequences later in the PS2 fixture by 124 updates for Bond and
133 for Dyne. The existing S01 `--bomb-delay` changed from 14 to 138 for Bond and to 147 for
Dyne. Charge remained 138 updates. The first Rose Pod then appeared at the same relative
tick in each pair. The first hostile bullet appeared one update later in PCSX2 in both pairs.
The stock PS2 game still advanced 600 times in 600 refreshes on both corrected routes.

| Phase-aligned rule | Fit on | Held out | Matches | Misses | Extra events | Score |
|---|---|---|---:|---:|---:|---:|
| Count threshold | Bond | Dyne | 0 | 3 | 0 | 0% |
| Count threshold | Dyne | Bond | 0 | 6 | 3 | 0% |
| Fractional budget | Bond | Dyne | 2 | 1 | 41 | 4.55% |
| Fractional budget | Dyne | Bond | 0 | 6 | 0 | 0% |

The phase-aligned budget fits also yielded zero holds on the Stage 1 capture. Matching those
early landmarks still leaves different object populations. At release, the active enemy slot
counts for MAME and PCSX2 were 181 and 121 on Bond and 191 and 143 on Dyne. In the MAME trace,
the combined profiled simulation and draw work excluding the setup wait had a median of 16
timer ticks before a hold and 13 before an advance in each route. The timer resolution is about
1 ms.

### Measure PS2 simulation and drawing

Build and select the S01 EE cycle recorder profile. Cold boot and arm it as for the workload
recorder. Export the three timing columns with `--cycles`.

```sh
python3 research/phase22/build_slowdown.py 'Ibara (Japan).iso' --measure-cycles \
  --output /path/to/pcsx2/cheats
python3 research/phase22/workload_capture.py arm
python3 research/phase22/workload_capture.py export ee-cycles.csv --cycles
```

The recorder reads CP0 Count at the start of native simulation (`0x0012E5CC`) and drawing
(`0x0012E1EC`), and brackets the final draw call (`0x0012E464`). These are emulated EE counts in
PCSX2. They cover CPU work through the draw call. Measure GS rendering separately. The stock
Stage 1 run captured 300 full-speed samples. With the fixed hold probe active, all 12 holds
in a 24-refresh sample recorded zero simulation time, and drawing ran on every refresh.
[PCSX2 CP0 Count update](https://github.com/PCSX2/pcsx2/blob/v2.8.2/pcsx2/COP0.cpp#L524)

Two timed Bond runs restored from one paused checkpoint matched all 600 gameplay telemetry rows.
The median absolute difference between repeated measurements was 169 counts for simulation and
38 for drawing. Fresh boots produced different enemy and bullet counts during the boss setup.

Using the phase-aligned Stage 6 fixtures above, I paired MAME's decision to advance or hold with
the last completed PS2 update's timing. The medians below sum simulation and drawing before
the final draw call. Stage 1's median was 372,000 counts.

| Route | MAME advances | MAME holds |
|---|---:|---:|
| Bond C | 858,000 | 848,000 |
| Dyne B | 867,000 | 1,005,000 |

```sh
python3 research/phase22/assess_cycles.py \
  --case stage6-bond bond-cadence.csv bond-ee-cycles.csv \
  --case stage6-dyne dyne-cadence.csv dyne-ee-cycles.csv \
  --quiet stage1-ee-cycles.csv
```

The cycle threshold fitted on Bond matched one of Dyne's three events and added 20 extra events
for 4.35%. Fitting on Dyne and testing on Bond missed all six events. Both rules predicted zero
holds in Stage 1.

I also sampled two interior refreshes per short PCSX2 GS dump near four points on each aligned
route. The table counts MAME holds near the sampled point, from four gameplay ticks before the
capture hotkey through six after it. The two busy Bond samples submitted more GS primitives
than the six samples with zero nearby holds. Submitted area and texture-upload volume overlapped.

| Route | Hotkey tick after release | Nearby MAME holds | PS2 GS primitives |
|---|---:|---:|---:|
| Bond | 120 | 0 | 998–1,015 |
| Bond | 220 | 11 | 1,644–1,646 |
| Bond | 320 | 6 | 1,453–1,456 |
| Bond | 471 | 0 | 1,308–1,312 |
| Dyne | 121 | 0 | 976–993 |
| Dyne | 220 | 0 | 1,246–1,256 |
| Dyne | 320 | 0 | 1,298–1,311 |
| Dyne | 471 | 0 | 1,273–1,306 |

The short captures cover Bond's sustained slowdown. A continuous measurement would let us
score primitive count against the entire route, including Dyne's isolated holds.

### CV1000-B and PS2 hardware timing

Ibara's CV1000-B uses a 102.4 MHz Hitachi SH7709S and an EP1C12 FPGA blitter. The SH-3
shares a 16 KiB, four-way cache between instructions and data, with 16-byte cache lines.
The blitter has its own video memory and can also take the CPU's work-RAM bus during texture
uploads. Cache misses, writebacks, and bus stalls affect how soon the SH-3 can publish its
next draw list. [SH7709S hardware manual](https://www.renesas.com/en/document/mah/sh7709s-group-hardware-manual) ·
[Ibara board configuration](https://github.com/mamedev/mame/blob/mame0289/src/mame/cave/cv1k.cpp#L91) ·
[PCB blitter and bus measurements](https://buffis.com/docs/CV1000_Blitter_Research_by_buffi.pdf)

The PS2's 294.912 MHz Emotion Engine has separate 16 KiB instruction and 8 KiB data caches,
64-byte cache lines, and 16 KiB of scratchpad RAM. Its DMA controller transfers graphics
packets through the GIF to the Graphics Synthesizer, which renders using 4 MiB of local
memory. The PCSX2 EE probe measures emulated CPU time through the draw routines. The GS
captures report submitted commands. Both can serve as proxies for modeling the arcade
workload. [Sony clock and GS specification](https://sonyinteractive.com/en/press-releases/2003/emotionengine-and-graphics-synthesizer-used-in-the-core-of-playstation-become-one-chip/) ·
[Sony EE Core manual](https://github.com/ninjadynamics/PS2Docs/blob/main/EE_Core_Users_Manual.pdf) ·
[Sony EE Overview, GIF and DMA](https://github.com/ninjadynamics/PS2Docs/blob/main/EE_Overview_Manual.pdf)

### Check the draw deadline in MAME

Set `IBARA_DEADLINE=bond-deadline.csv` with the Stage 6 fixture in MAME 0.289 `-drc`, alongside
`IBARA_CPU_ONLY=1 IBARA_RANK=0 IBARA_POST_RELEASE=600 IBARA_SIDE=1`. Repeat with
`IBARA_SIDE=2` and a fresh output path for Dyne. Set `IBARA_DEADLINE=stage1-deadline.csv`
on the Stage 1 fixture for the quiet control. Give each run fresh configuration and NVRAM
directories as above.

```sh
python3 research/phase22/summarize_cv1000_deadline.py \
  bond-deadline.csv dyne-deadline.csv stage1-deadline.csv
```

The callback samples the original game's display-list publication word at `0x0C283C94`
and the FPGA ready bit at `0x18000010` (SH-3 alias `0xB8000010`). For this MAME driver
the screen callback runs before IRQ2 is asserted. The next refresh sample shows whether
gameplay advanced after that deadline. The retail IRQ tests for publication sentinel
`0x19671010`, checks the list terminator, and checks ready bit `0x10` before kicking
the blitter. These samples bound the handoff at each IRQ. The CSV also records the
emulated screen time, the game's TMU checkpoints, and the SH-3 program counter. [MAME vblank callback order](https://github.com/mamedev/mame/blob/mame0289/src/emu/screen.cpp#L1674) ·
[Ibara IRQ routine](https://github.com/PaulAtreides67/ibara360/blob/main/gen/ibara_drc/recomp_02.c#L2843) ·
[MAME blitter ready bit and timer](https://github.com/mamedev/mame/blob/mame0289/src/mame/cave/cv1k_v.cpp#L810)

| Route | Intervals | Advances with both gates ready | Holds with list unpublished and blitter ready |
|---|---:|---:|---:|
| Bond C, Stage 6 | 800 | 600 | 200 |
| Dyne B, Stage 6 | 604 | 600 | 4 |
| Stage 1 control | 300 | 300 | 0 |

All three runs reproduced their earlier frame/tick sequences exactly. Bond first held at
refresh 162. Dyne held at 159, 362, 367, and 514. Every held refresh followed a deadline
sample with publication word zero and the blitter ready. Each advancing refresh followed
a sample with the publication sentinel and the blitter ready. This isolates the missed
draw-list handoff on these two MAME routes.

A second run with SH-3 program-counter sampling matched every deadline state. At 1,494
of the 1,500 advancing deadlines, the SH-3 was in the video wait loop at `0x0C04A0AA`.
It was elsewhere at all 204 missed deadlines. The draw-list emitter starting at
`0x0C062A70` accounted for 104 Bond misses and one Dyne miss. Another 30 Bond and two
Dyne misses landed in the list-building routine at `0x0C04F770`. This makes CPU time
spent generating arcade draw commands a concrete target for the PS2 workload model.
Capture that work separately from gameplay simulation and calibrate against independent
arcade routes. These samples measure deadline state and bracket publication to a refresh
interval. Exact publication and blitter completion timestamps and PCB timing remain open.
[SH-3 video wait loop](https://github.com/PaulAtreides67/ibara360/blob/main/gen/ibara_drc/recomp_00.c#L783) ·
[Draw-list emitter](https://github.com/PaulAtreides67/ibara360/blob/main/gen/ibara_drc/recomp_08.c#L122) ·
[List-building helper](https://github.com/PaulAtreides67/ibara360/blob/main/gen/ibara_drc/recomp_02.c#L1756)

### Fit the CPU cost of a draw list

Set `IBARA_DRAW_LIST=1` alongside `IBARA_DEADLINE` on the MAME 0.289 `-drc` commands
above. Keep `IBARA_CPU_ONLY=1` for Stage 6. The callback reads the finished
command list directly from SH-3 RAM once the game publishes it. A repeated
gameplay tick has an initial sample with no published list and a later sample
with the completed list. Pair the completed list with that tick's first video
deadline. The parser checks for exactly this sequence and requires the blitter
to be ready in these captures. The new reads reproduced the prior Bond, Dyne
and Stage 1 cadence traces frame for frame.

```sh
python3 research/phase22/assess_draw_deadline.py bond.csv dyne.csv stage1.csv \
  --holdout stage6-bond-rank200000 bond-rank200000.csv \
  --ee-cycles bond-ee-cycles.csv dyne-ee-cycles.csv
```

The two optional EE files are stock S01 exports with `--cycles` from the
release- and Rose Pod-aligned runs described above. The additional Stage 6
holdout uses Bond, `IBARA_SIDE=1 IBARA_RANK=200000 IBARA_POST_RELEASE=600`.

| MAME route | Advances / holds | Median sprite commands, advances / holds | Median draw time, advances / holds | Median simulation time, advances / holds |
|---|---:|---:|---:|---:|
| Stage 6 Bond, max rank | 400 / 200 | 1,580 / 2,318 | 7 / 9 ms | 6 / 8 ms |
| Stage 6 Dyne, max rank | 596 / 4 | 1,436 / 1,815 | 7 / 8 ms | 6 / 9 ms |
| Stage 1 control | 300 / 0 | 980 / — | 3 ms / — | 3 ms / — |

A linear fit to the native draw checkpoints gave 2.37 µs per draw on Bond
and 2.34 µs per draw on Dyne, in addition to a fixed term. The draw-time error
on the other route averaged 0.56–0.62 ms. Add the arcade's separately measured
simulation time and a fixed overhead fitted on the training route, then
compare that total to the 16.660 ms video period.

| Training → held-out route | Correct / actual holds | Extra holds | Slowdown event score |
|---|---:|---:|---:|
| Bond → Dyne | 3 / 4 | 1 | 40% |
| Dyne → Bond | 177 / 200 | 21 | 37.5% |

The arcade draw-count and command-mix models left Stage 1 at full speed. Splitting draws into visible, offscreen
and blended counts reduced timing error on Dyne slightly. On Bond it increased
misses at the event level despite correctly classifying more individual holds.
Using each previous update's estimate instead, the simple model classified
160 of Bond's 200 holds and none of Dyne's four on their exact gameplay ticks.
The same-tick result uses a list and timing samples available after the work
finishes. Separate linear calibrations from PS2 EE simulation and draw counts to
the corresponding arcade phases predicted zero holds on both held-out routes.

Even the game’s own elapsed checkpoint at a fixed deadline threshold
overpredicted individual holds by 22 on Bond and two on Dyne. That estimate
includes work through the checkpoint and uses a timer with roughly 1 ms
resolution. The checkpoint and first deadline shared the same timer value
on 90 max-rank Bond updates (45 advances, 45 holds) and eight max-rank Dyne
updates (seven advances, one hold). The publication bit sampled at the IRQ
distinguished them.

The independent rank-`0x200000` Bond run had 166 holds in 600 updates.
The draw-count rule classified 132 of them correctly when trained on max-rank
Bond and 136 when trained on max-rank Dyne. The rules added 47 and 52 extra
holds and scored 3.03% and 0% on events. These are emulator diagnostics.
PCB agreement and an automatic PS2 rule remain open.

For a PS2 predictor, the next measurements are the amounts of work produced by
individual CPU draw passes. The retail draw path begins at `0x0012E1EC`,
enters its 24-layer loop at `0x0012E234`, and reaches the final call at
`0x0012E464`. The combined EE timing can hide changes in how those passes
contribute to each frame.

### Measure PS2 draw passes

Cold-boot the retail ISO in PCSX2 with only the new S01 draw-pass profile enabled. The
production ISO patch uses the same manual slowdown gate and the research counters are
available through this PNACH profile.

```sh
python3 research/phase22/build_slowdown.py 'Ibara (Japan).iso' \
  --measure-draw-passes --output /path/to/pcsx2/cheats
python3 research/phase22/workload_capture.py arm
# Pause PCSX2 at the end of the capture.
python3 research/phase22/workload_capture.py export stage1-ps2.csv --draw-passes
```

The stock profiling path always advances gameplay according to the retail timing gate. Leave
the manual enable word at zero for these captures. For the two Stage 6 captures, restore the
flying-form checkpoint, seed the ship and rank as above, and arm with `--bomb-delay 138`
for Bond or `--bomb-delay 147` for Dyne, plus `--charge-ticks 138 --shot-ticks 360`.
Capture at least 600 gameplay ticks after release. Use the MAME fixtures above with
`IBARA_DRAW_LIST=1` for the corresponding arcade traces.

| Boundary | What is measured |
|---|---|
| `0x0012E1EC` | Start of the retail draw path |
| After `0x0012E234` | Setup done, 24-layer loop about to run |
| `0x0012E424` | Layer loop done, overlay and HUD pass starting |
| `0x0012E464`, before and after call | Start and end of game-side finalization |

The exporter reports CP0 Count deltas and differences in the active sprite-slot counter
at `$gp-29172`. The retail increment at `0x00110F18` follows insertion of a sprite into
its draw queue. The pool caps the count at 3,000. These are software queue entries, so
GIF transfers, VU work and GS execution remain distinct. The cursor at `$gp-28600` belongs
to a different retail list path and stayed flat in the Stage 1 probe.

```sh
python3 research/phase22/assess_draw_deadline.py mame-bond.csv mame-dyne.csv mame-stage1.csv \
  --ee-draw-passes bond-ps2.csv dyne-ps2.csv stage1-ps2.csv
```

PCSX2 2.8.2 captured 300 stock Stage 1 updates and 600 stock updates after Hadou
release for each Stage 6 ship. Both Stage 6 runs used the same restored PS2
checkpoint. All three runs advanced every refresh. In the 24-refresh forced
control, 12 updates held and the draw passes still ran on every refresh.
The timing components summed to the full draw interval in every stock sample.

| PCSX2 route | Layer CP0 counts, median | Overlay CP0 counts, median | Layer slots, median | Overlay slots, median |
|---|---:|---:|---:|---:|
| Stage 1 | 243,556 | 33,155 | 506 | 53 |
| Stage 6 Bond | 583,566 | 29,612 | 964 | 46 |
| Stage 6 Dyne | 556,396 | 29,788 | 913 | 46 |

The MAME cadence again matched the prior traces. Fit the arcade draw phase to
the PS2 pass timings or sprite counts, fit arcade simulation to PS2 simulation
time separately, then test the combined budget against the opposite ship.

| Model and held-out ship | Correct / actual holds | Extra holds | Event score |
|---|---:|---:|---:|
| Pass timing, Dyne | 3 / 4 | 297 | 0% |
| Sprite slots, Dyne | 3 / 4 | 317 | 14.29% |
| Pass timing, Bond | 0 / 200 | 0 | 0% |
| Sprite slots, Bond | 0 / 200 | 0 | 0% |

Both models left the Stage 1 control at full speed, and using the previous
update's estimate left their event scores unchanged. Supplying measured arcade
simulation time left the best event score at 9.09%. These are same-checkpoint
PS2 runs with fixed scripted Hadou release. The first Rose Pod in each new run
appeared one gameplay tick later than in the previous PS2 captures. The first
hostile bullet in the new Dyne capture appeared 301 ticks after release, versus
two ticks before release in the earlier capture. The mismatch limits the
comparison. Match both landmarks and reproduce the enemy sequence across
fresh checkpoints before treating these scores as a limit of the model.

## Accuracy check

The [timing audit](../phase17/README.md#arcade-slowdown-investigation-2026-11-23) records the retail
baseline. For a release comparison, use held-back original-board windows, including quiet gameplay
and distinct patterns from late Stage 3 and the Stage 5 and 6 bosses.

### Score timing traces

Write `window,frame,tick` CSV rows with one observation per refresh. Give equivalent windows the
same name on both systems. Anchor row 0 immediately after the same gameplay landmark and close on
the same advancing gameplay tick relative to the anchor. The tick itself can start at any
nonnegative value. Equal consecutive tick values indicate a held refresh.

```sh
python3 research/phase22/score_slowdown.py pcb.csv candidate.csv --reference-kind pcb
```

Holds separated by up to four advancing refreshes form one slowdown event. A match needs onset
within four refreshes and held-refresh count within 20% of the reference. Events are matched
one-to-one, in order, within each window. The score is matches divided by matches plus missed and
extra events. Quiet windows contribute any false events the candidate creates. A reference with
zero events leaves the PCB target unscored. Use `--reference-kind diagnostic` for emulator and synthetic
traces. The JSON includes the first differing refresh and each unmatched event. PCB mode exits
successfully only at 80% or above.

I ran the scorer on the two PCSX2 Stage 1 traces from the same restored checkpoint. The control
advanced six ticks in six refreshes. The forced run advanced six ticks in twelve refreshes and
its first hold was at refresh 1. The scorer reported one event with six held refreshes, counted it
as a miss when the stock trace was the candidate, and counted it as extra when the traces were
reversed. Matching the forced trace against itself scored 100% in diagnostic mode.

### Original arcade superplays

INH's *The Lunatic Ibara* DVD contains KMT's Bond run in title 3 and Y.S.333's Dyne run in title 4.
The web preview is 29.97p. The original MPEG-2 samples
below decode as 720×480, 29.97 interlaced frames per second, top field first, with 3,003-tick steps
on the 90 kHz clock throughout the sampled interiors. The disc image used for the field check was
`INDV_0111.ISO` (SHA-1 `67da4aa7cfd80df1feb3346e7d1de9ffe9c56a42`). [Archive catalogue](https://archive.org/details/indv-0111)

| DVD title 3 sample | Chapter | Title VOB sector |
|---|---:|---:|
| Stage 3 Valley terrain and early enemies | 3 | 299685 |
| Late Stage 3 Valley, bomb and suicide sequence | 3 | 412051 |
| Late Stage 5 Castle, boss firing sequence | 5 | 730467 |
| Stage 6 Garden, boss segment | 6 | 780000 |
| Stage 6 Garden, dense boss attack | 6 | 800000 |

For the disc image above, the title VOB starts at absolute disc sector 79456. Extract a short
sector range from a local copy, then run the audit with FFmpeg and NumPy installed.

```sh
dd if=INDV_0111.ISO of=stage6.vob bs=2048 skip=$((79456 + 798000)) count=5500
python3 research/phase22/audit_superplay.py stage6.vob --crop 332:360:54:66
```

The audit checks the field clock and top-field-first marking, crops away the graphics alongside
the game, registers the two line lattices, and reports stretches of at least eight alternate
fields with much less luma change than their neighbors. Source timestamps are MPEG-2 PTS and can
reset across DVD titles. In the Stage 5 sample, a cyan pickup moved left and down through ten
consecutive fields, including top-to-bottom transitions within encoded pictures. The DVD's
59.94 fields per second and the PCB's 60.024 Hz differ by about one refresh per twelve seconds.

| Run and sample | Title VOB sector | Sector count | Observed field cadence |
|---|---:|---:|---|
| KMT Stage 3 scrolling | 299685 | 2100 | No sustained repeats detected |
| KMT Stage 6, first Hadou launch at the flying form | 780000 | 5500 | Two short runs of 11 and 33 repeated pairs in the first 12 s after release |
| KMT Stage 6, Teresa's flying form | 798000 | 5500 | 527 repeated pairs across 17.6 s at PTS 1992.3707–2009.9383 |
| Y.S.333 Stage 6 approach | 1630000 | 4200 | No sustained repeats detected |
| Y.S.333 Stage 6, Teresa's flying form onset | 1665000 | 8500 | 449 consecutive repeated pairs across 15.0 s, continuing at the cut |
| Y.S.333 Stage 6, continuation of the previous sample | 1671000 | 10000 | The overlapping run ends at PTS 1949.9450. A change of field parity and further repeats follow. |
| Y.S.333 Stage 6, later in the same fight | 1713500 | 4200 | No sustained repeats detected |

The main KMT and Y.S.333 intervals reproduced with separate crops of the left and right halves of
the playfield. The long KMT interval has moving projectiles and pickups under a Hadou Gun trail.
The Y.S.333 onset shows the rose stem collapsing after the flying form emerges, as a Hadou Gun
trail and Rose Pods fill the screen. Y.S.333's run later returns to a stretch with motion on both
fields while Teresa is still firing. Treat these as evidence for approximately half-rate gameplay
in specific portions of the fight and use the faster segments as controls. A single cadence for
the whole phase would add slowdown during those controls.

The first Hadou launch beside the detached boss gives a direct test of a timer keyed to phase
and weapon use. The launch is visible within decoded fields 285–294 for KMT and 99–108 for
Y.S.333 in the two onset samples. Over the following 720 fields, both KMT half-crops detected
44 repeat pairs. The Y.S.333 half-crops agreed on at least 278 and the full crop detected
286–291, depending on the chosen launch field. The first run that both half-crops detect starts
at least four seconds earlier relative to release for Y.S.333. A fixed offset and duration
from launch cannot meet the four-refresh onset and 20% duration tolerances on both routes.
These are two different play routes and ship configurations. A workload-based timing model
needs state beyond the phase and whether a Hadou Gun is active.

In a field-by-field close-up, a visibly rising Hadou rocket with a growing white exhaust is
present by field 284 in KMT's clip and field 101 in Y.S.333's. Use the visible rocket motion
as a common anchor when the original input edge is unavailable.

I tested a single-field workload proxy using the percentage of bright luma pixels in the
playfield. The threshold was fit on one player's clips, then tested on the other player's
clips. From KMT training to Y.S.333 validation, the frame-label F1 score was 0.742. Under the
event timing tolerances, it matched zero events and produced 32 extra and two missed events.
Reversing the roles yielded 0.638, zero matches, 19 extra, and four missed. The frame-label
score measures coarse overlap on the DVD. A brightness trigger fails the event check.

```sh
python3 research/phase22/compare_superplay_density.py \
    --train kmt-first.vob kmt-late.vob --validate ys-first.vob ys-boss.vob ys-stage.vob
```

Use the sectors in the table above, with `ys-first.vob` extended to 13,200 sectors starting at
1665000 so the first long slowdown run ends inside the sample. The Y.S.333 control clips start
at 1713500 and 1630000.

The audit detects visible repeat pairs. It does not recover exact simulation ticks from blended
or ambiguous fields, and both runs share the DVD mastering pipeline. Scoring needs the same
attack, ship and weapon use on both systems. Check the onset on moving projectiles and pickups,
account for any capture slips, and keep a separate source window for validation.

#### Replay DVD timing in PCSX2

`superplay_cadence.py` exports a timing window using only visible repeats that agree
across the full playfield and both halves. Each source field corresponds to one
refresh in this diagnostic. Unconfirmed fields advance during playback. The
sampled DVD rate is 59.94 fields/s and the arcade board runs at about 60.024 Hz,
so allow for capture timing and launch-anchor uncertainty in interpretation.

```sh
python3 research/phase22/superplay_cadence.py kmt-first.vob \
  --crop 332:360:54:66 --crop 160:360:54:66 --crop 160:360:226:66 \
  --anchor-field 284 --refreshes 719 --window bond --output bond.csv
```

Use `--anchor-field 101 --window dyne --output dyne.csv` for the Y.S.333 onset
clip (8,500 sectors from 1665000). KMT uses 5,500 sectors from 780000.
The confirmed Bond trace first holds at refresh 413 and has 44 holds in 719
refreshes. The confirmed Dyne trace first holds at refresh 162 and has 279 holds
in 719 refreshes. The stricter crop-agreement test excludes an eight-pair
precursor in the Dyne clip.

Cold boot with a newly built S01 `--capture` profile. Pause from a Stage 6 Arcade
Practice flying-form checkpoint and schedule the same bomb input on each run.

```sh
python3 research/phase22/workload_capture.py arm --bomb-delay 14 \
  --charge-ticks 138 --shot-ticks 360 --cadence bond.csv
```

The first cadence row is anchored to the PS2 gameplay tick immediately after
the bomb release. The game replays the hold schedule from RAM, allowing a full
update between any two holds, and resumes full-speed gameplay once the schedule
ends. For a stock control, restore the same paused checkpoint and arm with the
same bomb and shot arguments. Re-arming without `--cadence` clears the schedule.
The prescribed timing tests the PS2 update gate and can serve as a target when
evaluating an automatic slowdown rule.

In PCSX2 2.8.2, the Bond fixture advanced 675 updates in 719 refreshes with the
DVD schedule, including both short repeat runs. The Dyne fixture advanced 440
updates in 719 refreshes, including the sustained run. Both traces matched the
requested holds per refresh and resumed one update per refresh after playback.
The stock controls advanced the same number of updates with zero holds. At each
advancing tick, the captured inputs, player position, rank, bomb stock, enemy
counts, bullet counts, and item counts agreed with their stock control. The
matching rows cover charging, the release, playback, and the return to full speed.
This test uses seeded routes and supplies the slowdown timing from the DVD.
The 80% accuracy target applies to independently predicted slowdown events.

#### Testing an automatic workload rule

The short Dyne excerpt ends inside its first sustained slowdown. For a duration
test, extract 13,200 sectors from title VOB sector 1665000 and export the same
Dyne window with `--refreshes 1308`. The three crops agree on 539 holds from
refresh 162 through 1239. There are 69 following refreshes without confirmed
holds before the export ends. This window ends ahead of the next repeat run.

Capture stock Bond-left Type C at inverted rank `0x600000` and stock Dyne-right
Type B at `0x200000`, with the same checkpoint and scripted charge, launch, and
shot input. Record at least 675 gameplay updates after the post-launch anchor
for Bond and 769 for Dyne. Use the complete S01 workload CSVs so the fitter can
locate the logged bomb release and read the preceding samples.

```sh
python3 research/phase22/assess_workload.py \
  --case bond bond.csv bond-stock.csv \
  --case dyne dyne-long.csv dyne-stock.csv
```

The fitter checks thresholds on bullet, enemy, Rose Pod, item, and total
object counts. Each signal is tested as the current count, the sum over the
last eight gameplay ticks, and that sum's change from the preceding eight.
A value at or above the threshold inserts one hold before the corresponding
gameplay update. Each route is held out in turn. The report also fits both routes
together to show how well the family can fit those samples when both are
available. The seeded PS2 fixtures approximate the footage's routes.

On the full-duration test, neither fitted rule matched an event on the
held-out route. The best fit across both routes scored 25%, with one match,
two misses, and one extra event.

| Fitted on | Held out | Matched | Missed | Extra |
|---|---|---:|---:|---:|
| Dyne | Bond | 0 | 2 | 1 |
| Bond | Dyne | 0 | 1 | 18 |

The item-count rule fitted to Dyne started at the expected refresh 162
and held for 608 refreshes versus 539 in the DVD trace. Its final hold
arrived at refresh 1376, 137 refreshes after the DVD's last hold. The
existing 20% held-count tolerance scores this as a match. On Bond, the
same rule slowed the game from refresh 190, 223 refreshes ahead of the
first observed burst, and inserted 486 holds. Use these results as a
check on the sampled object-count rules. The initial game states, ranks,
and firing sequences in the DVD runs are only partially recoverable.

On the PS2 side, **ARCADE → PRACTICE → STAGE 5 → START POSITION BOSS** reached the Castle boss
encounter in PCSX2 with S01 off. At the first live read, the stage scene was 6, the transition
word was zero, and the enemy pool contained type `0x41` boss parts, including subtype `0x00`.
The sample was taken at gameplay tick 698. This gives a repeatable entry into the encounter
for finding a matching attack landmark.

For **Stage 6 → START POSITION BOSS**, the initial flower is enemy type `0x4A` and subtype
`0x00`. The flying form is `0x4A` subtype `0x0D`. The Rose Pod swarm appears as type
`0x4F` with subtypes `0x00` and `0x04` in the enemy slots. A fixture shortened the flower
phase with reduced HP for its parts, then let the engine spawn and animate the flying form.
With inverted rank around `0x600000`, S01 off, and P1 invulnerability refreshed in RAM, a
610-refresh capture from the flying form's spawn advanced the game's stage and outer loop
counters by 610 each. The run reached 135 sampled hostile bullet records and 95 active Rose
Pod slot pairs.

A second run charged and released a Hadou Gun during the same transition with stock updates.
The bomb stock fell from three to two. PCSX2 snapshots spanning the launch and the following
pod swarm captured 611 video refreshes, 611 outer-loop updates, and 611 gameplay ticks
(2147 to 2758). The position and weapon sequence differ from the DVD runs, so use this as a
baseline for the same mechanic. An overall accuracy score still needs matched, held-back
windows across multiple attacks.

A low-rank PCB run by Bond Type C is a candidate for locating comparable attacks. Check its capture
cadence before counting repeated frames. Buffi's board measurements also give a basis for separating
blitter cost from CPU waits. [PCB run](https://www.youtube.com/watch?v=xvNvVEqdghE) ·
[CV1000 blitter measurements](https://buffis.com/research/cv1000-blitter-research/)
