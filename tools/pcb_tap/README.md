# PCB input tap: record and replay a real board's inputs, compare its slowdown with MAME

The goal is to measure how far MAME's CV1000 slowdown is from a real Ibara PCB, scene by scene, on real gameplay
(research/phase22). The kit has three parts:

* a Raspberry Pi Pico that records the JAMMA inputs once per video frame, and can replay them;
* a direct video capture, used to find the frames where the board held an update (slowdown);
* PC tools that turn both into one input word per game update, replay that in MAME, and compare the holds.

**Status:** the PC side has been checked in MAME. A MAME run standing in for the board went through the whole
pipeline, and the replay reproduced it exactly: 8,999 of 8,999 refreshes with the same ship position. The hold
handling is unit-tested. The firmware and wiring have **not** been tested on hardware yet.

## Parts (about $20–40, plus a capture setup)

| Part | Count | Job |
|---|---|---|
| Raspberry Pi Pico (RP2040), MicroPython | 1 | logging and replay, USB to the PC |
| JAMMA extender / pass-through (male edge ↔ female edge) | 1 | taps the lines without cutting the harness |
| 74LVC245A (5 V tolerant inputs, Ioff) | 2 | reads the 5 V input lines into 3.3 V |
| 2N7000 N-MOSFET, 100 Ω gate resistor, 100 kΩ gate pull-down | 9 each | "presses" a line during replay |
| LM1881 sync separator, 680 kΩ (Rset), 0.1 µF ×2, 1 kΩ + 220 Ω, 10 kΩ + 20 kΩ | 1 set | vertical sync for the Pico |
| Perfboard, headers, wire | | |

Do not use a RECO or any remap/autofire device in the chain while recording or replaying. The log would then not
match what the game reads.

## Wiring

Find the signals on **your** harness's JAMMA pinout. Published tables disagree on some pins
([Neo Geo Dev wiki](https://wiki.neogeodev.org/index.php/JAMMA_connector_pinout),
[Museum of the Game](https://www.arcade-museum.com/pinouts-class/JAMMA)), so check each line with a meter: an
input reads about 5 V when released and 0 V when its button is held.

Signals used: P1 up, down, left, right, buttons 1–3, P1 start, coin 1 (9 inputs), plus video sync and GND.

| Bit | Signal | Sense (74LVC245 B output → Pico) | Drive (2N7000 gate ← Pico) |
|---|---|---|---|
| 0 | P1 up | GP2 | GP12 |
| 1 | P1 down | GP3 | GP13 |
| 2 | P1 left | GP4 | GP14 |
| 3 | P1 right | GP5 | GP15 |
| 4 | P1 button 1 (shot) | GP6 | GP16 |
| 5 | P1 button 2 (bomb) | GP7 | GP17 |
| 6 | P1 button 3 | GP8 | GP18 |
| 7 | P1 start | GP9 | GP19 |
| 8 | coin 1 | GP10 | GP20 |
| — | vertical sync (LM1881 pin 3 via 10 kΩ / 20 kΩ divider) | GP22 | |

* **Pass-through.** Each input runs straight through the extender, from the cabinet or supergun to the PCB. The
  tap only listens, or pulls the line low. Nothing is cut.
* **Sense.** Each line goes to a 74LVC245A A input. Power it at 3.3 V from the Pico, DIR to 3.3 V, OE to GND. Its
  B outputs go to the Pico. The A inputs tolerate 5 V, and Ioff keeps the chip safe while the Pico is unpowered.
* **Drive.** Wire each 2N7000 drain to the line, its source to GND, and its gate to the Pico pin through 100 Ω,
  with 100 kΩ from gate to GND so the line stays released while the Pico boots. Gate high pulls the line low,
  exactly like a closed button.
* **Sync.** The JAMMA video sync (TTL composite) goes through 1 kΩ, with 220 Ω to GND (about 0.9 V), then 0.1 µF
  to LM1881 pin 2. Wire pin 4 to GND and pin 8 to the supergun's +5 V. Put 680 kΩ from pin 6 to GND and 0.1 µF
  from pin 6 to GND. Take the vertical sync from pin 3 through 10 kΩ, with 20 kΩ to GND, into GP22.
* **Ground and power.** Join the Pico GND to the supergun GND. Power the Pico from USB only; **never** connect
  the Pico's 5 V (VBUS/VSYS) to the supergun's +5 V.
* Wire everything with the power off. Before connecting the PCB, check with a meter that no Pico pin sees more
  than 3.3 V.

## Software

* Firmware: flash MicroPython to the Pico and copy `firmware/main.py` to it.
* PC: Python 3.10 or later, plus `pip install pyserial` (tap.py) and `numpy` + `ffmpeg` (held_frames.py).
* MAME: the original Ibara set (`ibara`, U4 `d5fb6657`), pinned to one version. Phase 22 used 0.289, and later
  versions changed CPU and memory timing.

## Capture

Run RGB from the supergun into a capture path that keeps the board's **60.024 Hz** frames one to one: an OSSC or
RetroTINK into a capture card, or a 15 kHz-capable card.

Many HDMI paths drop or repeat a frame now and then to hold 60.000 Hz, and a repeated frame looks exactly like
slowdown. **Check this before anything else.** Record a long attract-mode run with the tap logging. Then confirm
that `held_frames.py` reports almost no repeats, and that its count of non-blank frames equals the tap's frame
count. `to_updates.py` warns when they differ.

## A measurement run

```
python3 tools/pcb_tap/tap.py record --port /dev/ttyACM0 --out run1.tap   # then switch the PCB on; play; Ctrl+C
# start the video capture before switching the PCB on as well
python3 tools/pcb_tap/held_frames.py capture.mkv --crop W:H:X:Y --out run1.frames   # crop: playfield only
python3 tools/pcb_tap/to_updates.py run1.tap run1.frames --out run1.updates [--offset N] [--lag 1]
UPDATES=run1.updates OUT=run1.mame PLAYER=0x0C283794 \
    mame ibara -rompath ROMS -nonvram_save -autoboot_script tools/pcb_tap/mame_replay.lua
python3 tools/pcb_tap/compare.py run1.updates run1.mame --window 300
```

* **Same start.** Use the same DIP settings and NVRAM in MAME as on the board, and start both from power-on. The
  game's random sequence may depend on frames since boot.
* **Sync check.** With `PLAYER` set, the MAME output carries the ship's position per refresh. If the replay
  diverges (the ship ends up somewhere other than on the video, or dies), try `--lag 0` / `--lag 2`, then
  `--offset`. Also check that the capture neither dropped nor repeated frames.
* **Replay on the board:** `tap.py play --port ... --log run1.tap`, then switch the PCB on. Replay the same log
  twice and compare the two captures; that shows whether the board itself is repeatable.

## Files

| File | |
|---|---|
| `firmware/main.py` | Pico firmware: record or replay one input word per vsync |
| `tap.py` | PC side of the tap: `record`, `play` |
| `held_frames.py` | held (repeated) frames in a capture |
| `to_updates.py` | per-refresh inputs + held frames → per-update inputs |
| `mame_replay.lua` | replays per-update inputs in MAME and logs MAME's own holds |
| `compare.py` | PCB vs MAME holds per window of updates; matched hold events |

Update counters: base Ibara `0x0C21F880` (phase 22). Black Label `0x0C2380B0` is incremented next to BL's main
loop (`0C06CDE8`), but it isn't yet confirmed in a slowdown scene: a hard-rank run through stages 1–2 produced
no holds in MAME 0.289.
