# K49 handoff follow-up

The baseline is 28322bce on Claude's branch. K48 Arrange CONFIG and the K49 graze sound are already
in that build. The original PS2 checklist has 18 tests. The K49 Python patcher completed locally
with the full Black Label zip and produced a 3,932,848,128-byte ISO. PCSX2 2.8.2 booted
this ISO and entered Noir Stage 1.

## Black Label Stage 1 Hadou controls

Ran MAME 0.276 with separate fresh configuration and NVRAM directories. All three trials used
the Phase 24 script with no held shot, fixed rank 0x600000 until the input, and three bombs at
the start. Each had two active enemy bullets on the first sample. Button 2 was never pressed,
pressed for six frames, or pressed for 140 frames.

| Trial | Peak type 3 medals visible | Peak type 7 roses visible | Peak type 11 items visible |
|---|---:|---:|---:|
| No bomb | 0 | 0 | 0 |
| Six-frame bomb | 1 | 2 | 1 |
| 140-frame button hold | 23 | 0 | 25 |

These are peak concurrent objects observed in 31 snapshots per trial, sampled 20 frames apart.
The longer hold consumed a bomb by frame 20, before the scripted release. Type 11 also appeared
in the short-bomb trial. Distinguish the actions using projectile state and their overall item
patterns before using item counts to compare the ports.

    OUT=hadou.txt MODE=hadou NOSHOT=1 mame ibarablk -rompath ROMS -video none -sound none \
      -nothrottle -nodrc -skip_gameinfo -autoboot_delay 0 \
      -autoboot_script research/phase24/bl_rank_bomb.lua

Repeat with MODE=none and MODE=bomb. Keep the captures and patched ISO local.

## K49 Noir Stage 1 preview

PCSX2 input inspection verified Circle set processed bomb bit 0x0020 with the loaded key
configuration. The short press after native tick 1,200 emitted projectile IDs 5 and 9 alongside
ID 0 and early roses. With a 140-tick hold, the first read after release that contained projectiles
showed ID 0 and roses. A later no-bomb-control sample also contained ID 0 and roses, and stock
changed in that control. The run left collision and respawn logic active. These observations
identify a confound in the Stage 1 window and leave Noir's actual Hadou drop path unresolved.

For the matched experiment, keep P1 invincible through the full capture, record the accepted
charge/release branch and bomb fragment counter, and use per-frame item allocations. The current
snapshots are useful for finding candidates and cannot attribute every item to the action.

## Integration order

Stage 6 rose parity depends on the barrage and a paired timer comparison. The Stage 1 Hadou
result above gives a short run for checking the drop path. Repeat item measurements at matched
stage encounters once the PS2 projectile branches are positively identified. The damage audit,
pod launch counts and graze cadence remain separate items on the updated handoff. Slowdown is paused.

## Original PS2 checks added to the handoff

The new checks cover Noir's shared KEY CONFIG and second-player ship select, Arrange's four CONFIG rows
and continue behavior, and graze sound during dense play. The full checklist is in
[the K49 handoff](../../docs/HANDOFF_2026-11-25.md#hardware-test-list-original-ps2-patcher--clean-iso----bl-rom-with-u23u24-in-the-zip).
Hardware verification remains pending.
