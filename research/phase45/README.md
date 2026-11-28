# K62 Noir replay controller trace

This follows the [Phase 44 handoff](../phase44/README.md#for-codex) at
1b28c35. The experiments use a disposable PCSX2 profile and a local test
disc. The normal builder and patcher still use the K62 gameplay build.

## Stage 1 call path

| Address | Role |
|---|---|
| 0x00116C90 | Advances the fixed-point scroll accumulator at 0x00338DD0 by the current step at 0x00338DD8. |
| 0x00115808–0x00115878 | Reads the stage script cursor at 0x00338E00, compares the event timing against the scroll accumulator, and dispatches the command. |
| 0x001EAC10 | Special script command table entry for 0x001155E0. |
| 0x00115600 | Calls the type-76 factory at 0x00163350. A zero return rewinds the script cursor to retry the command on the next update. |
| 0x00163370 | Checks residency of resources 0x346, 0x372 and 0x385 using the list referenced at 0x00205BC4. The resource check queues missing assets. |
| 0x00163398 | Reserves five slots from the 192-entry enemy pool after the resource check succeeds. |

The trace records both attempts and successful creation. It snapshots
the scroll state, script cursor and enemy slot 3 before each of the
first 1,200 game updates. The factory and its two checks record their
returns at the call sites. The report also compares the regular replay
checkpoints for score, rank, stage tick, RNG, position and bomb stock.

## Reproduction

Build from a clean Japanese ISO with the MIPS cross toolchain available.
Add --bl-rom with your own Black Label zip to include Noir's arcade assets.

    python3 research/phase45/build_trace.py 'Ibara (Japan).iso' replay.iso \
      --symbols replay-symbols.json --controller-trace

Use one disposable PCSX2 profile per experiment. Start and return from
one Practice game in the chosen mode. The fixture ignores that game.
Play the next Practice game to record it, then choose RETURN MENU from
pause. Start the same Practice stage again to replay the input. Save a
local PCSX2 state once the replay has reached the recorded length.

    python3 research/phase45/report_trace.py playback.p2s replay-symbols.json \
      --controller-trace

Add --factory-events to see every retry. Pair each savestate with the
symbols from its own build. For an intentional one-update delay, build
with --delay-controller as well as --controller-trace. The positive
control makes the first successful resource check in playback ask the
stage interpreter for one extra retry. The probe still logs the real
native resource-check return.

## PCSX2 2.8.2 results

Each run used Stage 1 Practice and the original three-game sequence.
Inputs were taken from the recording in each pair. The replay driver
held shot while cycling movement during the recording. Checkpoints
cover updates 0–1,199 individually, then 1,200 and 1,500.

| Run | Recorded updates | Checkpoint mismatches | First successful factory call, record / play |
|---|---:|---:|---:|
| Arcade control | 1,689 | 0 / 1,202 | 446 / 446 |
| Noir control, factory trace | 1,686 | 0 / 1,202 | 446 / 446 |
| Noir, resource and slot probes | 1,690 | 0 / 1,202 | 446 / 446 |
| Noir, unlimited playback speed | 1,696 | 0 / 1,202 | 446 / 446 |
| Noir, full Black Label zip, null renderer | 1,688 | 0 / 1,202 | 457 / 457 |
| Noir, full Black Label zip, OpenGL | 1,685 | 561 / 1,202 | 460 / 457 |
| Noir, one forced retry | 1,685 | 554 / 1,202 | 446 / 447 |

The factory made its first attempt at update 414 in all these runs.
With the narrower probe, Arcade and Noir each showed 32 calls that
returned zero before creation. The resource and slot probes attributed
all 32 retries to asset residency. Enemy-slot allocation succeeded on
its first call. The full-zip run needed 43 resource retries. The
null-renderer pairs agreed, including the run with the frame limiter
disabled during playback.

### Natural slip with OpenGL

The OpenGL/llvmpipe pair reached the factory at update 414 in both
runs with the same scroll accumulator and script cursor. The
recording had 46 failed residency checks and first succeeded at 460.
Playback had 43 failed checks and first succeeded at 457. Both
allocated all five enemy slots on their first attempt after assets
were available. At update 458 the cursor and slot 3 diverged, with
type 76 already active in playback. Score and RNG first diverged at
641. No stage-tick mismatches occurred.

This capture localizes a natural early Noir slip to asset residency
at the factory. The first-ready update can move within the same
record/play pair. The renderer settings describe the run and do
not establish that OpenGL causes the underlying timing change.

### Controlled slip

In the positive control, native resource readiness was already true
at update 446 during playback. The fixture made the command retry
once, moving successful creation to 447. At the start of update 447
the recording had advanced its script cursor and slot 3 held type 76.
Playback still pointed at the pending command and slot 3 was inactive.
The scroll accumulator and step still agreed at that update. Score first split at 647 (10
versus 0), and RNG first split at 657. All stage-tick checkpoints
agreed. That establishes that one extra factory retry is sufficient
to cause an early replay slip. The independent late graze or kill
difference still needs a pair that matches through the early window.

Next trace insertion of the three required IDs into the
512-halfword residency table at 0x00448F80 and correlate it with the
asset request and completion. A replay synchronization experiment
needs to handle assets arriving on both sides of the recorded
creation update.
