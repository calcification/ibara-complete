# Phase 43 — Input lag: PS2 vs MAME vs PCB (Claude, 27 November 2026, in progress)

## Method

A/B from one savestate: run A with no new input, run B with a direction held from frame 1 on. The game is
deterministic, so the screens match until the input shows; the first differing displayed frame gives the lag.
"Lag N" below: the input is held from frame 1 and frame N + 1 is the first changed frame.

## MAME (Black Label, ibarablk)

`mame_lag_ab.lua`, stage-6 checkpoint, shot held, P1 Right: frames 1–3 identical, frame 4 differs, so **3 frames**
in MAME's CV1000 model. The real board can differ (MAME's video timing is a model): the PCB tap kit can measure it
the same way (the Pico presses the input, the capture finds the changed frame).

## PS2 (PCSX2, Noir)

`pcsx2_lag_instrumentation.diff` (local PCSX2 build, research only): `LAG_AT` / `LAG_BIT` press a pad bit from a
given EE vsync after launch, at the emulated pad response (so the game's whole pad path through the IOP is
measured); `LAG_HASH` logs, per presented frame, a hash of both display circuits' framebuffers (software renderer)
tagged with the EE vsync number of that frame (passed through the MTGS vsync packet). `pcsx2_lag_ab.sh` boots
PCSX2 straight from a savestate (Noir stage 1, current patched ISO).

* Two runs without input: identical on every frame (one display circuit has a one-byte difference on some frames,
  ignored).
* The game ignores the pad for ~380 vsyncs after a savestate load (presses at 200 and 210 both first showed at
  379): measure after that.
* Right pressed from EE vsync 500: first changed presented frame 503. From 510: 513. **3 frames**, as in MAME.

PCSX2's pad and display timing are themselves models; the host's presentation (and the user's display chain) adds
to both systems equally and is not counted here.

## So far

| System | Input to first changed frame |
|---|---:|
| MAME (Black Label) | 3 |
| PS2 (PCSX2, Noir) | 3 |
| PCB | to measure (tap kit) |

The PS2 port does not add internal frames compared with MAME's model. Reducing below 3 would make it faster than
MAME's arcade model; whether that matches the real board waits for the PCB measurement.
