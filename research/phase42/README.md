# Phase 42 — Load screens: the game-side loop (Claude, 26 November 2026)

Follows phase 18 (disc and IOP buffers: no gain). Question: does the game's own loop slow loading down?

## The load queue service

`0x0010D520`, called once per frame from both frame loops (`0x00113398`, `0x00117058`), does one step per call:
with a read in flight (flag `0x00339D90`) it checks the stream status and, when done, runs the entry's callback;
otherwise it takes the next entry from the load ring (`0x0033AF20`, 1,113 slots), issues the read (`0x001BCA00` /
`0x001BCE20`) and sets the flag. A release ring (`0x0033E350`) is serviced first.

## Measurements (PCSX2, disc timing on, Arcade NORMAL to stage 1)

`load_pump.c` (this folder; wired into the kuro executable only for these tests): a stub after each retail call,
scene-change log with CPU-clock timestamps.

| Variant | First NOW LOADING | Opening (scene 1) | Stage-1 load (scene 2) |
|---|---:|---:|---:|
| Retail (one call per frame) | 2.7 s | 6.7 s | **6.2 s** |
| Call again while work, up to 10 ms per frame (spins on the read in flight) | 4.0 s | 6.7 s | **9.8 s** (worse) |
| Call again only when idle with queued entries (never waits on a read) | 2.7 s | 6.7 s | 6.2 s (no extra calls happened) |

Spinning starves whatever completes the reads. In the no-spin variant the queue was never non-empty while idle:
entries are queued one at a time from above.

Stage-1 load window, counted per call (both loops call, so about half are frames): a read in flight in 593 calls,
idle with an empty queue in 150; 76 archive entries (~11 MB). So ~80 % of the load is waiting on reads (the IOP
streaming chain, ~4 frames per entry); at most the idle ~20 % (~1.2 s) is reachable from the EE side, and the two
variants above did not reach it.

## Conclusion and options

* The EE frame loop is not the bottleneck. Shipped build unchanged.
* Remaining levers: (1) the IOP streaming modules (MTSFILE / CDVDACCS chunk handling; phase 18's bound: the 5–6 s
  stage load could at best drop to ~2 s on PCSX2 timing) — deep IOP work, results must be checked on hardware since
  real drive timing differs; (2) time to gameplay that is not loading: the ~6.7 s opening scene before the stage-1
  load (in Noir it carries BL's select screen and takeoff).
