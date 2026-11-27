# Phase 43 — Input lag: PS2 vs MAME vs PCB (Claude, 27 November 2026, in progress)

## Method

A/B from one savestate: run A with no new input, run B with a direction held from frame 1 on. The game is
deterministic, so the screens match until the input shows; the first differing displayed frame gives the lag.
"Lag N" below: the input is held from frame 1 and frame N + 1 is the first changed frame.

## MAME (Black Label, ibarablk)

`mame_lag_ab.lua`, stage-6 checkpoint, shot held, P1 Right: frames 1–3 identical, frame 4 differs, so **3 frames**
in MAME's CV1000 model. The real board can differ (MAME's video timing is a model): the PCB tap kit can measure it
the same way (the Pico presses the input, the capture finds the changed frame).

## PS2 (to do)

Same A/B needs frame-exact input and per-frame display hashes in PCSX2: a local PCSX2 build option that forces a pad
bit from a given vsync after a state load and logs a hash of each displayed frame. Then read the game's pad and
frame loop to see where any extra frames come from (pad read timing, draw / flip buffering).
