# K61 homing target guard and Stage 2 slot lifetimes

This audit uses Claude's K61 at 2fa705e. It compares the shipped K61
hook, the guarded hook, and Black Label in MAME over three seeds per
weapon. Each exposure is 1,000 Stage 2 updates with stationary Bond A,
shot level 2, three matching pods, and starting rank 0x800000.
All runs made 1,500 allocation attempts.

## Shared aim branch

The native target lookup at 0x00134344 writes the returned target index
to the pod at +40. A miss falls through to 0x00134364 with heading zero.
A hit computes the target heading and branches from **0x00134474** to
**0x00134368**. Both routes execute the delay-slot store of the desired
heading at +38.

K61 replaces the shared branch at 0x00134368. Its original hook
overwrote the delay-slot heading with the formation angle even on a
hit. Every valid-target sample in the K61 trace showed a formation
heading. The fix repeats the native signed target-index test and
retains the desired heading when the lookup returned an index below
192. The no-target branch still supplies both outer formation headings
and the center D-pad lookup from K61.

| Homing build | Launches per 1,000 updates (seed range) | Target samples with formation heading |
|---|---:|---:|
| Black Label MAME | 549.0 (540–558) | 149 / 5,829 |
| Shipped K61 | 559.0 (539–593) | 7,971 / 7,971 |
| Guarded K61 | 441.0 (406–473) | 80 / 7,665 |

The guarded counts reproduce the Phase 36 stationary prototype seed for
seed. The occasional formation angle with a valid target also occurs in
MAME because the calculated target angle can coincide with formation.
When a target was lost in MAME, the desired heading changed immediately
and the actual heading was still turning in all 27 recorded cases.
Guarded K61 did the same in all 21 recorded cases. Acquisitions
were 36 in MAME and 21 with the guard. The two engines use the same
fixtures with different enemy pools, so target indices and transitions
are comparable as counts and local behavior.

## Slot lifetimes

Track active shot flags and kinds across 48 slots. Arcade write taps
timestamp each allocation and free, including within-update reuse.
The PS2 cohort uses frame-end births and free transitions. Its
snapshot birth totals equal the instrumented allocator counts in
all 12 runs. Completed lifetimes exclude slots active at the start
and slots still occupied at the end. Kind 0 is the hit spark in these
runs. It remains in the same occupied pool and can block a launch.

| Weapon and build | Launches | Mean projectile slots occupied | Mean spark slots occupied | Mean allocation to free |
|---|---:|---:|---:|---:|
| Homing, arcade | 549.0 | 13.53 | 3.85 | 30.77 updates |
| Homing, shipped K61 | 559.0 | 14.25 | 2.50 | 28.60 updates |
| Homing, guarded K61 | 441.0 | 12.27 | 4.60 | 36.67 updates |
| 5-way, arcade | 1,270.0 | 34.89 | 7.66 | 33.39 updates |
| 5-way, both K61 builds | 1,118.3 | 31.93 | 8.48 | 36.16 updates |

Both native allocators collect free slots in ascending order anywhere
inside each pod's search limit. 5-way needs any five free slots among
16. The trace shows a longer slot residence in both guarded homing and
5-way, plus more slots held by sparks. The guarded homing gap remains
19.7% and the 5-way gap remains 11.9% in this window. The guard leaves
the 5-way trace unchanged. The next comparison can separate the
projectile's flight, contact and spark expiry paths before making
further gameplay changes.

## Reproduction

Use the [Phase 36 checkpoints and runner](../phase36/README.md).
For MAME set POD_TRACE to an output path such as runs/bl/3-1.trace
in addition to OUT. Run weapons 3 and 6 with seeds 1–3. For the PS2
build add BL_POD_AUDIT_LIFETIME and use --trace-save with the slot 8
path, keeping the source checkpoint in slot 7. Leave
BL_POD_AUDIT_FALLBACK off to exercise the shipped implementation
on each branch. Checkout 8f529c6 to build the shipped K61 trace or
use this branch tip for the guard. The trace files contain 1,000 records of 66 bytes,
with 48 slot kinds and nine little-endian halfwords in groups of
target ID, desired heading and actual heading. The optional MAME
events file stores a little-endian update halfword, slot byte, and
allocation flag byte per event.

    python3 research/phase41/report_lifetimes.py \
      --cohort runs/bl --cohort runs/ps2 --cohort runs/ps2-guard

The local cross compiler rebuilt the two baked profiles for the release
patch. The hook and patcher suite passed 25 checks. The existing XTC
PNACH generation check still fails with this compiler.


## Hardware patch

The [patcher files](../../patcher/) contain the guarded build. Use the
patcher with the Japanese retail ISO and full ibarablk.zip. The builder
and patcher outputs matched byte for byte with that zip. The scratch
verification used a sparse copy of the source ISO. The output is
3,932,848,128 bytes. SHA-256 with the full zip:

    dd5220f737c622e19cbf31a4a117bb8ab9eaf1889ef58ef78f564f81e0ef060d

A PCSX2 boot of the release executable verified the guarded jump was
installed on entering Noir and the retail branch was back on entering
Arcade. In hardware test H13c, hold shot with homing pods equipped
between waves, then keep holding as an enemy appears. Outer pods
should swing from formation toward the enemy. When the last target
disappears, they should turn back to formation. Move in eight
directions during a gap to exercise the center pod.
