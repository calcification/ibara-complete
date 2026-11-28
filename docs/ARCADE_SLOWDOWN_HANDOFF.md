# Arcade slowdown handoff for Claude

Work is on [codex/arcade-slowdown-config](https://github.com/calcification/ibara-complete/tree/codex/arcade-slowdown-config), based on Claude's K40/K41 line. The latest console test ISO is built by the checked-in standalone patcher. Its last gameplay change was the menu reset in `0a8ad65`. [Patcher instructions](../patcher/README.md)

## Original PS2 and emulator results

- **K41 was the last complete original PS2 pass.** The K40 disc with `--bl-rom` passed Mode Select and Exit, all three Practice menus, Noir returning to Arcade, ship select and takeoff, P2 join and Continue, rank and effects, Yoko and both Tate directions, and save isolation. [K41 runtime report](../tests/results/2026-11-20_RUNTIME.md#k41--original-ps2-hardware-pass-2026-11-23)
- **Later console feedback.** Josh's CRT photo showed the cramped Noir plaque. Commit `5ce9d68` spaced the words and cleaned the metal background. The new plaque was checked in PCSX2 and Josh subsequently reported that everything seemed right apart from Arcade half speed carrying over after leaving to the menu. That report reproduced the carry-over on the earlier build.
- **Newest patch on hardware.** A repeat of the menu-reset sequence on the original PS2 remains pending. Start with Stage 1, set Slowdown On, activate half speed, Exit through the pause menu, and re-enter Arcade. The stage should start at full speed, and a fresh L2 + R2 press should re-enable half speed. [Console checklist](../tests/manual/ARCADE_SLOWDOWN_PS2.md)

| Current slowdown checklist | PCSX2 2.8.2 result |
|---|---|
| Config starts Off, the chord has no effect, Exit wraps and confirms | Passed on the integrated patch. Off retains the two original timing branches. |
| Config On and L2 + R2 in Arcade Practice | Passed. The stage starts full speed, goes to 30 updates per 60 refreshes, then returns to 60/60. A held chord fires once. |
| Shot and bomb edges during holds | The S01 retail probe carried a bomb release through a held refresh and consumed one bomb. Its same-checkpoint Stage 6 playback preserved the advancing-tick input edges and sampled gameplay state, including shot and bomb. |
| Pause, resume, and Pause → Exit while half speed is active | Passed on the `0a8ad65` build. Pause and resume kept half speed. Exit cleared the override and retained Config On. The next Arcade Practice stage advanced 60/60 with the chord held through loading, then 30/60 after release and a fresh press. |
| Arcade Normal and Noir isolation | Arcade Normal toggled to half speed on the reset build. Noir Config kept its own Exit row and hid Slowdown in the initial integrated check. Returning from Noir restored Arcade's setting. |
| Arrange Practice chord and reset-build console retest | Still open as explicit checklist observations. |

The original disc patch stays at the retail ISO size. The latest research uses an optional PCSX2 PNACH recorder on the clean retail image.

## Slowdown research

**Note from Claude's replay tests (28 November):** the frame counter 0x00338CDC, the pad block's auto-repeat flags and
Arcade rank creep advance per refresh, not per update, so they keep full speed during a hold (weapon-item cycling,
autofire timing). Details and a fix pattern: [phase 44](../research/phase44/README.md#for-the-slowdown-work-what-counts-refreshes-not-updates).

The PS2 runs its native game and can hold core updates while rendering and polling pads. The current console build exposes the manual half-speed test. Automatic slowdown needs a predictor that clears the project's 80% event target on independent reference captures.

MAME 0.289 on the original Arcade parent set held 200 refreshes on max-rank Bond and four on max-rank Dyne, over 600 gameplay updates each. Stage 1 held zero out of 300. All 204 holds occurred with the SH-3 draw list unpublished and the blitter ready at the video IRQ. Both routes reproduced their earlier cadence exactly. An independent rank-`0x200000` Bond capture added 166 holds. [Deadline trace and model](../research/phase22/README.md#check-the-draw-deadline-in-mame)

An arcade-only fit based on sprite-command count estimated native draw time with roughly 0.6 ms average error across the two ships. Adding the arcade's measured simulation time gave 37.5–40% event scores. The independent rank test scored 0–3.03%. The arcade game’s profiling checkpoint and the deadline sometimes share the same roughly 1 ms timer value on opposite outcomes. The actual publication bit remains the label. The two phase-aligned EE totals also missed every held-out hold.

The new draw-pass recorder measured Stage 1 and both Stage 6 ships in PCSX2. The layer pass accounted for most of the measured draw time. The pass-timing and sprite-slot models scored 0–14.29% on the opposite ship and produced zero Stage 1 holds. The fresh Dyne run's first hostile bullet was at +301 ticks after Hadou release, compared with −2 in the earlier capture. The first Rose Pod was within one tick. Matching both landmarks and the enemy sequence is the next reproducibility check. [Commands, measurements and held-out scores](../research/phase22/README.md#measure-ps2-draw-passes)

## Where to pick up

Use the pass recorder and evaluation under [Phase 22](../research/phase22/README.md#measure-ps2-draw-passes). Retain the time and queue counters separately. The sprite counter at `$gp-29172` tracks queued entries from the active PS2 renderer. The legacy list pointer at `$gp-28600` stayed flat in the Stage 1 test. The renderer's shared pool is capped at 3,000 slots.

Keep the first live hostile projectile as the Stage 1 landmark. For Stage 6, compare the Hadou release and first Rose Pod tick before interpreting cross-system errors. The scripted checkpoint seeds ship, rank, stock and position, and is valuable for repeatability. Add a distinct phase or stage when evaluating a model for release. The original PCB still needs matched timing evidence.
