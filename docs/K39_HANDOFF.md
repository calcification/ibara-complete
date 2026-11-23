# Ibara Complete — K39 handoff for Claude

Start from `codex/kuro-presentation` at [commit `aaa0344`](https://github.com/calcification/ibara-complete/commit/aaa034409196c0b3b1d7b9869de08d9edfe04c77). GitHub’s file tree matches the tested local build. Josh is planning to test this build on an original PS2. The [debug handoff](DEBUG_HANDOFF.md) and [runtime results](../tests/results/2026-11-20_RUNTIME.md#k39--start-input-and-selector-texture-leases) have the detailed evidence.

## What changed and what passed

- **Menus and saves.** Noir is the third Mode Select row and has its own **NOIR MODE** submenu title. PCSX2 passed the retest for highlighting and confirming Exit, which previously froze on hardware. Arcade, Arrange, and Noir each have Practice. Instrumented Noir Normal and Practice Game Overs preserved the retail rankings, play data, and memory-card image.
- **Video and HUD.** NTSC Tate R and Tate L output 240 active progressive lines. Yoko stays interlaced with filtering off. Noir’s bombs and fragments sit above the weapon bar, the `1P` score has a margin, and the fixed XTC text was removed. Attract hides the rank gauge. Noir hides the stage-name line.
- **Ship select and co-op.** P1 picks a ship before takeoff. Either controller’s Start button leaves the selector running, and K39 removes the premature P2 prompt. P2 presses Start during gameplay and gets the ship set in **CONFIG → FIGHTER TYPE**. P1 Continue resumes gameplay directly, matching the MAME check. Selector texture slots released at all six stage starts. The final standalone patch rechecked Stages 1 and 6.
- **Load times.** The disc-buffer trials established no repeatable speedup. The build uses the retail layout. The [load research notes](../research/phase18/README.md) record where to measure the disc-read and DMA waits if work resumes there.

## Where to pick up

Use the hardware results to prioritize the old Exit freeze, Tate gameplay framing and diagonal shimmer, and the Noir ship-select-to-gameplay transition. For co-op, try P2 Start once during selection and again after takeoff. If checking save isolation, use a spare card. The known visual issue is the pink **NOW LOADING** banner behind Stage 1’s selector. Busy-stage texture cache behavior still needs longer play coverage.

Use the [standalone patcher from the tested commit](https://github.com/calcification/ibara-complete/tree/aaa034409196c0b3b1d7b9869de08d9edfe04c77/patcher) with the clean Japanese ISO and `--bl-rom ibarablk.zip` to exercise the selector and Black Label rank art. The tested ISO is exactly **3,932,848,128 bytes**, and all **50 tests** passed. Keep the repository source-only and preserve the retail ISO size.
