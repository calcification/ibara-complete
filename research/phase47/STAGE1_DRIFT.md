# Noir replay drift at the Stage 1 texture-queue wait

The release REPLAY menu's first observed RNG difference at sampled
update 720 followed a script timing difference hundreds of updates
earlier. The per-update probe used PCSX2 2.8.2, the Null renderer, the
full Black Label zip, normal Noir GAME START, a real memory-card save,
and the real REPLAY menu. An assisted run kept the player alive and
requested native game-over teardown to save at a predictable point.
Update indices start at zero at the Stage 1 replay boundary.

The Stage 1 script cursor reached the same command at 0x001EB03E on
both sides. Command FF27 calls 0x00114820, which allows the script
to advance when the texture-loader queue head at 0x00448700 equals
0x0800. A zero return makes the native interpreter retry next update.
The texture loader services this queue separately from gameplay.
A repeat with the queue head traced saw the same sequence of 74 head
values. The first change was at update 7 in recording and 11 in
playback. The four-update gap persisted through the empty status,
which arrived on update 346 in recording and 350 in playback.

| Event | Recording | Playback |
| --- | ---: | ---: |
| First update with the script past FF27 | 347 | 351 |
| First update with nonzero scroll | 351 | 355 |
| Type-76 factory's first attempt | 413 | 417 |
| Type-76 factory creates the controller | 445 | 449 |
| RNG calls from 0x0012447C | 692 | 696 |
| First different RNG seed at update start | 693 | 693 |
| First different score at update start | 735 | 735 |

Both sides had 32 type-76 residency retries and zero failed pool
allocations. The four-update delay was already present before the first
type-76 request. Through all 1,200 traced updates the recorded and
decoded input fields had the same hash, and the stage tick and player
position matched. At update 693 the recording's RNG seed was 2627500045
and playback's was 808381751. The first different score was 630 versus 0.
The probe also replayed the prior 3,150-update file byte-for-byte from
the memory card. Its playback checkpoints matched the previous run
through update 1,170, and its script, factory, and RNG calls followed
the same delayed playback schedule.

[Phase 45](../phase45/README.md) found a separate timing difference
when the factory starts together and its own resource requests
finish on different updates. The FF27 wait precedes those requests.

## Same-file control

The original 3,150-update save (checksum 901e2d41) was played again
with FF27 targeted to update 346. The diagnostic let the native loader
run for five render-only passes at that update, leaving the replay
input and stage tick parked. The command advanced during update 346
and the type-76 factory first ran at update 413.

The original recording and controlled playback agreed at the
update-720 and update-750 checkpoints. The first sampled RNG mismatch
moved from 720 to 780, where the score and tick still matched.
The controlled run had 79 mismatching checkpoints out of 105
(81 without the control) and ended with score and RNG differences.
All 3,150 inputs decoded. In this playback, type 76 was created on
update 444 after 31 residency retries. In the traced recordings
above, creation was at 445 after 32 retries. The old save lacks a
per-update factory trace on its recording side, so the later RNG
difference cannot be assigned to that one-update spawn difference
from this pair alone.

## Reproduction

Build with the MIPS cross toolchain, a clean Japanese retail disc,
and the full Black Label zip.

    python3 research/phase47/build_drift_probe.py 'Ibara (Japan).iso' drift.iso \
      --bl-rom ibarablk.zip --symbols drift.json

Record at least 1,200 updates in a normal Noir GAME START. Use a
temporary memory-card profile. Capture a PCSX2 save state at the
save prompt, save the replay, and play it from Noir's REPLAY menu.
Capture a second save state once playback returns to the menu.
The probe traces 1,200 updates per side, including the stage script
cursor, scroll, input hash, texture-wait and factory results, and RNG
call sites. The report validates that both states contain the same
replay and that all its inputs decoded.

    python3 research/phase47/report_drift.py record.p2s playback.p2s drift.json

For a control playback of the same file, use the probe symbol
`drift_gate_target` and write the recording's FF27 advance update
plus one before entering REPLAY. The one-based value is also
available in `drift_gate_recorded` in the recording capture. The
probe blocks early successes and allows up to 120 render-only
passes at the target update if textures are late. The rendering path
can also call the stage interpreter, so the control keeps FF27 parked
during those passes. Only the Stage 1 FF27 wait at 0x001EB03E is
controlled. The replay file uses the usual
format 3. No diagnostic is enabled in the production patcher.
