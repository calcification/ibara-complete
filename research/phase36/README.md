# Stage 2 pod projectile census

Base is K60 at 3b72c39. The diagnostic measures 5-way, homing, and
napalm for three seeds each in a 1,000-frame Stage 2 window. Both
engines use stationary Bond A, three pods of the given weapon, shot
level 2, held shot, and stored rank 0x800000. MAME reaches Stage 2
naturally. PCSX2 enters through Practice. The matching seeds make
each engine's runs repeatable.

The frame-end census watches the 48 P1 pod-shot slots for off-to-on
changes in the selected projectile type. A slot may retire a shot
and launch another before the next sample. The independent allocation
census sees these launches.

| Weapon | Weapon byte / pod kind | Projectile type | Shots per successful call | Slots searched per pod |
|---|---|---:|---:|---:|
| 5-way | 6 / 12 | 2 | 5 | 16 |
| Homing | 3 / 6 | 4 | 1 | 6 |
| Napalm | 4 / 8 | 7 | 1 | 4 |

MAME counts the first slot read in each call to 0x0C0718C0, filtered by
the weapon's native caller. It separately counts each write that
activates a previously empty pod slot. The PS2 dispatch table at
0x002102D0 sends pod kinds 12, 6 and 8 to 0x00134B40, 0x00134C00 and
0x00134BC0 respectively. The PS2 probe wraps the corresponding
allocator calls at 0x001337B8, 0x00132EE4 and 0x00133FD4. A successful
allocation is followed by a fixed-size volley at each of those sites.

## Reproduction

Run MAME 0.276 in interpreter mode. Use a fresh Stage 2 checkpoint made
1,000 stage callbacks after native stage byte 3 begins, with the natural
input and locks in the Stage 1–5 damage audit's checkpoint helper.
The Lua script selects the weapon with the arcade change input, writes
the seed 1,000 updates after restore, and compares the following
stage-frame window equivalent to 2,500–3,499.

    mkdir -p runs/bl
    RESUME_STATE="$PWD/stage-2.sta" WEAPON=6 SEED=1 OUT=runs/bl/6-1.txt \
      mame ibarablk -rompath ROMS -nodrc -video none -sound none -nothrottle \
      -skip_gameinfo -autoboot_delay 0 -autoboot_script research/phase36/bl_pods.lua

Repeat for weapon 3, 4 and 6 with seeds 1–3. The first output row has the
weapon, seed, exposure, allocations, sampled births, occupied-slot
frames, attempts, position, and ship. Other rows identify projectile
writers.

Build the PS2 diagnostic and select POD TEST, then Arcade Practice
Stage 2. Save an unarmed state in slot 7 near tick 900. Use PINE with
a dedicated PCSX2 profile. The diagnostic sets the weapon at tick
1,200, sets the seed at tick 2,000, and samples ticks 2,500–3,499.

    python3 scripts/build_ee_hooks.py --elf 'Ibara (Japan).iso' \
      --define BL_POD_AUDIT --bake-elf bl_mode PODS.ELF
    python3 research/phase04/build_menu_probe.py 'Ibara (Japan).iso' \
      --payload-elf PODS.ELF --label 'POD TEST' --output pod-test.iso
    python3 research/phase36/ps2_pods.py slot07.p2s runs/ps2
    python3 research/phase36/report_pods.py runs/bl runs/ps2

## Matched Stage 2 results

Each row covers three seeds with 1,000 updates each. Position was
(66, 480) when the window opened in all 18 runs. Success is the
fraction of allocation attempts with space for a full volley.

| Weapon | Engine | Allocations (range) | Sampled | Attempts | Success | Mean alive |
|---|---|---:|---:|---:|---:|---:|
| 5-way | MAME | 1270.0 (1270–1270) | 1167.0 | 1500.0 | 16.9% | 34.89 |
| 5-way | PCSX2 | 1118.3 (1115–1125) | 1118.3 | 1500.0 | 14.9% | 31.93 |
| Homing | MAME | 549.0 (540–558) | 426.0 | 1500.0 | 36.6% | 13.53 |
| Homing | PCSX2 | 373.3 (361–384) | 373.3 | 1500.0 | 24.9% | 12.38 |
| Napalm | MAME | 209.7 (207–212) | 46.3 | 1500.0 | 14.0% | 11.94 |
| Napalm | PCSX2 | 199.7 (198–203) | 199.7 | 1500.0 | 13.3% | 11.63 |

The original frame-end sampler missed 8% of arcade 5-way allocations,
22% of homing allocations, and 78% of napalm allocations in these
windows. It saw every PS2 allocation in the same windows. This
changes the interpretation of the Phase 16 and Phase 26 counts.
The measured attempt rate was 1,500 for each weapon in each engine,
with the same fixed volley sizes and slot search limits.

Noir launched 11.9% fewer 5-way, 32.0% fewer homing, and 4.8% fewer
napalm projectiles. For homing, the occupancy/launch ratio was about
33 ticks in Noir and 25 frames in MAME. That ratio describes time
spent occupying slots as homing projectiles. Native hit sparks can
continue to occupy slots after the projectile changes type. The
allocation success rate isolates room for the volley as the immediate
difference. It gives no reason to raise the firing cadence.

## Homing without enemies

The test clears enemy flags from the start of this weapon window.
Use POD_EMPTY=1 for MAME and add --define BL_POD_AUDIT_EMPTY for
PCSX2. Use --weapon 3 in the PS2 runner for the homing-only cohort.
The window, positions, seed points and shot settings are the same
as the live-enemy measurements.

With empty target pools MAME launched 1,160 homing shots in each of
three replays. Noir launched 513 each time. The arcade uses its
formation angle when its target query returns no target. The two
outer homing pods have stationary angles 288 and 224 (out of 512),
with the center pod aimed at angle 0. Noir's equivalent no-target
branch at 0x00134364 supplies angle 0 to all three pods.

The opt-in BL_POD_AUDIT_FALLBACK switch changes that zero-angle result
for stationary homing tests. It applies to that branch only. The
trial uses the same native allocator and target query.

| Homing condition | MAME | K60 | Stationary fallback |
|---|---:|---:|---:|
| Stage 2, enemies active | 549.0 (540–558) | 373.3 (361–384) | 441.0 (406–473) |
| Stage 2, enemy pools cleared | 1160.0 (1160–1160) | 513.0 (513–513) | 1159.0 (1159–1159) |

Each result covers three 1,000-update replays. The fallback recovered
about 39% of the live Stage 2 gap and brought the no-target run within
one projectile. A valid target still uses the native aim path. The
measurement supports a formation-angle correction for homing. The
remaining live gap and the smaller 5-way gap need projectile lifetime
and target-selection traces before changing firing or slot limits.

To repeat the A/B run, add --define BL_POD_AUDIT_FALLBACK to the
diagnostic build, then use --weapon 3 for the PS2 runner and report.
Repeat with and without BL_POD_AUDIT_EMPTY. The opt-in code is limited
to stationary input pending direction and target-transition testing.

With the arcade enemy pool cleared, a second trace read each pod's
desired heading (offset 38 in its 48-byte record) five updates into
a cardinal input. The outside pods held 288 and 224 in all four cases.
The center pod used 256, 0, 128 and 384 for up, down, left and right.
This identifies the center pod's directional behavior for a follow-up
implementation. The K60 and diagnostic branch default builds produced
identical cave words and hook sites for both bl_mode and kuro.
