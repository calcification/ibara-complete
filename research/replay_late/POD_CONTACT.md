# Noir pod targeting during replay

The original missed contact is described in [the late replay trace](README.md).
The follow-up fixture samples the P1 pod records, 48 pod projectiles, and
enemy slot 3 immediately before the pod collision pass at 0x0012E61C. It
samples Stage 1 entry and updates 2,000–2,766. The event trace also records
the actual shot slot and target at 0x0012B520, before the shot becomes a spark.

## Reproduce

    python3 research/phase45/build_trace.py 'Ibara (Japan).iso' pods.iso \
      --bl-rom ibarablk.zip --symbols pods.json --controller-trace \
      --sync-controller --stage-one-entry --late-trace --event-start 2470 --pod-contact

Use the fixture to record and replay a normal Noir Stage 1 run past
update 2,766. The survival-assisted tests used PCSX2 2.8.2, held shot,
and alternated left and right. They disabled P1 collision deaths in the
emulator for both the recording and its playbacks.

    python3 research/replay_late/report_pod_contact.py playback.p2s pods.json
    python3 research/phase45/report_trace.py playback.p2s pods.json --controller-trace

For the controlled comparison, save the emulator state at the menu
after recording and before starting playback. Load it for each repeat.
Set the 32-bit fixture symbol replay_contact_restore_pods through PINE
before entering the next game. Zero gives the original behaviour,
one restores the six pod records at Stage 1 entry, and two restores
the target search cursor alone. The recording is the same for both
playbacks.

## Trace results

The Null renderer capture first showed a pod projectile difference
at update 2,493. The three pods selected enemy slots 2, 7 and 9 in
record and 19, 26 and 34 in playback. Shot slot 35 diverged at 2,499,
then contacted enemy slot 26 only in playback at 2,511. Score and RNG
differed at the start of 2,512. OpenGL also reproduced different
initial pod headings, with its first projectile difference at 2,118.

A paired comparison restored the full pod records and eliminated the
stale record bytes at entry. The first active shot still split at
2,554 and the first score and RNG difference remained at 2,578, with
the same values as the control. The captured target flags, kinds and
positions also agreed during the first eight updates with active pods.

The native selector at 0x00137DA0 returns a cached target if it
qualifies. For a new target it increments the shared 16-bit cursor at
0x00338B98, scans enemy slots in that order, and leaves the cursor at
the selected slot. Its other explicit writer wraps the cursor at 192
within the same function.

## Cause confirmed

Both playbacks used the same 3,170-update recording and started from
the same menu save state. The control entered Stage 1 with search cursor
37, while the recording entered with 0. Its first shot trajectory split
at 2,497, followed by an extra contact at 2,515 and a 10-point and RNG
difference at 2,516. The early type-76 synchronization passed and the
fixture recorded zero update-timing misses.

Restoring only the search cursor at Stage 1 entry put both sides at 0.
The stale pod record bytes were still present at entry, and the first
eight sampled target sets had the same flags, kinds and positions.
All 1,207 checkpoints matched, as did the per-update score and RNG
throughout the 3,170 recorded updates. The ordered event window
matched 666 RNG advances, 106 damage events, 36 pod contacts,
nine XTC awards and four retail grazes per side.

The search cursor carries over from earlier target searches and was
missing from the replay's initial state. A new shot can aim at a
different eligible enemy even with the same input, seed and enemy
positions. Preserve this cursor with the recorder's start state when
integrating the change. This test covers a one-player PCSX2 Stage 1
run on the K65 baseline. Full-stage transitions and original hardware
remain separate validation cases.
