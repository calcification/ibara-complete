# Noir replay trace for the late Stage 1 divergence

Phase 44 reported a graze or kill one update apart near 1,070–1,078.
Phase 45 synchronizes the earlier type-76 spawn before this window. The late trace records ordered events for every
game update from 1,000 through 1,127 in the same Stage 1 Practice pair.

## Reproduce

Build from a clean Japanese PS2 ISO with the MIPS cross toolchain and
your full Black Label zip. Keep the output and symbol files local.

    python3 research/phase45/build_trace.py 'Ibara (Japan).iso' noir-late.iso \
      --bl-rom ibarablk.zip --symbols noir-late.json \
      --controller-trace --sync-controller --late-trace

In PCSX2, choose Noir, then Practice, and start Stage 1. Return to the
Practice menu from the first game. Record the second game with shot held
and some movement. Play past update 1,500 and use RETURN MENU. Start the
same stage and let the fixture replay the recording. Save a PCSX2 state
after playback reaches the recording's length.

    python3 research/phase46/report_events.py replay.p2s noir-late.json

Add --require-match to fail on a gameplay or event difference. The
report identifies the first differing update and event in the trace
window, alongside the first gameplay checkpoint or RNG-seed difference.
Game events on the same update are compared in execution order.
Checkpoints at the start of an update reflect score changes through
the previous update. The trace rejects truncated records.

## What the trace covers

| Event | Capture point and fields |
| --- | --- |
| RNG | Seed advance at 0x00111050. Record caller, bound and new seed. Events after the stage dispatch are marked as between updates. |
| Enemy damage | Four calls to 0x001278B0. Record caller, slot, damage amount, HP before and after, and the lethal return flag. |
| Noir XTC | Sample the side, shot-held timer, pod count and player flags at the XTC test. Record each accepted bullet, its distance from the player, and the graze box size. |
| Retail graze | The +10 score paths at 0x0012A92C (bullet) and 0x0012ABD8 (enemy contact). Record side, object slot and updated score. |

The retail game can add 10 points even when Noir's XTC test accepts no
bullets. The two retail sites and XTC use the same sound routine. Their distinct
trace events identify the source of the points.

The trace stores at most 8,064 events per side in 256 KiB total. The
initial fixed-width prototype truncated a burst of 195 events at update
1,038 in one run. The final layout lets a busy update use the shared
capacity. Unit tests cover that burst size, a one-update graze shift,
and rejection of a truncated trace.

    python3 research/phase46/test_report_events.py

## PCSX2 2.8.2 captures

| Capture | RNG advances per side | Damage outcomes per side | Checkpoint mismatches |
| --- | ---: | ---: | ---: |
| Null renderer, frequent direction changes | 642 | 1,058 | 0 / 1,202 |
| OpenGL, Phase 44 snapshot cadence restored | 509 | 74 | 0 / 1,202 |
| Null, later movement patterned after Phase 44 | 680 | 106 | 0 / 1,202 |

All captures matched the ordered events and had zero update timing
misses. Each ran 128 XTC eligibility checks. The later-movement pair
also matched six retail bullet grazes between updates 1,023 and 1,031.
The historical divergence remains open.

## Normal Game Start and the Stage 2 transition

A survival-assisted smoke test reached Stage 2 in recording and
playback. The recording moved into Stage 1 at update 570, and
playback at 484. The type-76 factory consequently ran 86 updates
apart. The first score and seed mismatch was at update 1,141.
The pair had 286 timing misses and 172 mismatches among 1,226
checkpoints. Its clocks had diverged before Stage 1, so it does
not isolate a difference at the Stage 2 boundary.
