# Phase 44: replays (Claude, 27 November 2026)

Question: can a game be recorded as inputs and replayed exactly on the PS2, for replay saves (memory card)?
Answer so far: yes for Arcade, and almost always for Noir, once a few timing and start-state leaks are closed.
The code is `ps2/hooks/replay.c`. It is test-only: nothing ships, and the release image is unchanged.

## Method

A test build (scratchpad scripts, see "Tools") adds `replay.c` to the kuro hook and three call sites. In
PCSX2 it plays one Practice game (ignored), records a second with scripted inputs, quits with RETURN MENU, and
replays the recording in a third. Games 2 and 3 are entered the same way. Game 1 (entered from the frontend) is
not used, because its rank behaves differently from later games.

Checks:
* A checkpoint every update up to 1,200, then every 300: score, rank, scene and stage tick, seed, and P1 position
  and bombs.
* RAM snapshots in both runs, either every 50 updates (globals 0x00338000–0x00340000 and the pools
  0x00440000–0x00470000) or a full 2 MB at one update. Only active objects are compared.

## What makes a replay drift, and the fix for each

| Leak | Evidence | Fix in replay.c |
|---|---|---|
| Polls per update vary with timing. The pad is polled from the vsync wait (0x00113390 → 0x00112A80), once or twice per game update depending on timing. | The same game polled twice per update in one run and once in another, from update 758. | Record and replay per **game update**. The hook is at the start of the update path, 0x0012E5CC (`jal 0x00138CD0`). |
| The pad state block at 0x00341FA0 (2 × 0x50: current, previous, pressed, auto-repeat and its timers) is rebuilt per vsync. The shot code reads its auto-repeat flags directly. | The shot pool differed by update 925 with identical player button words. | Store the block (40 words) per update and write it back before the update. Also store the player records' button words (+0x24C to +0x254) and the raw pad values (returned to the pad reads during playback, so the live pad cannot steer or pause). |
| Arcade rank creep runs in the loop path (0x0012E478 to 0x0012E880), and its step depends on timing. | Rank fell by 17 units per update in one run and 16 in the other, from tick 380. | Store rank per update and write it back. |
| The frame counter 0x00338CDC ($gp-28692) counts vsyncs. Weapon-item type cycling and item handling read it. | Same item, same spawn update, different type (3 vs 0); its cycle counter advanced +2 vs +1 per 50 updates. | During a game, count updates instead: undo the vsync increment in the pad hook and add 1 per update. Restore it at the start. |
| Start state carried over from the previous game: inputs pressed before the first update (ship select). | P1 +0x264/+0x265, the 120-frame double-press window of the 0x10 handler at 0x0013B3E4. | Save both player records (2 × 0x290) at the first update and restore them. This also fixes ship and bomb choice. |
| Start state: unused fields in object slots keep data from the previous game; items survive RETURN MENU. | Enemy +0x7C and bullet +0x4C in reused slots; one extra active item at the first update. | At the first update, clear all shots, items and bullets, and the inactive enemy slots. |
| Start state: spawn serial 0x00338E50 (next to the enemy group counter 0x00338E4C). | 70 apart between runs; copied into each bullet at spawn. | Store and restore 0x00338E4C–0x00338E53. |
| Start state: item drop state. The stage's item initialiser 0x00132640 zeroes the bytes 0x00338E54/55/58/59/5C and the tables 0x00495120–0x0049513F; Practice's GAME START skips it. | Drop counter 3 vs 0 at the first update; restoring that one byte alone made things worse, because the tables still differed. | Zero all of them, and clear the item pool, at the first update (**shipped, K62**). |
| Rank set at game init: 0x00338EB8 += rand(2), drawn before the first update. | 0x10 vs 0x11. | Store and restore 0x00338EAC–0x00338EBB. |
| Our XTC graze test (xtc.c) checks one side per update, alternating, and kept its phase from the previous game. | +10 graze one update apart (update 1078). | `xtc_reset()` at the first update (**shipped, K62**). |
| Our boss-cancel tracker (bl_enemy.c `bc_hp`, `bc_left`) persists between games. | (Found by reading; it could clear bullets at the start.) | `bl_enemy_reset()` at the first update (**shipped, K62**). |

The seed (0x00337D08) is stored and restored at the first update. Recording starts at that first update, after
loading and ship select, so neither is in the replay.

## Results

* **Arcade Practice, stage 1:** an exact match at every checkpoint through update 1,500 (the recording was 1,785
  updates; score 7,280, same seed).
* **Noir Practice, stage 1 (1,822 updates):** an exact match through update 1,800 in most runs (e.g. score
  15,230 and 11,820, same seed). One intermittent slip remains: in some runs the RNG is one step apart from
  update 704. It is preceded by an enemy (type 0x0D, subtype 0x10, slot 0) whose animation frame and x position
  are one update apart at update 650. Under investigation.

### The open Noir slips (status 28 November)

Over about 30 runs of the latest test build, roughly 40 % match exactly through update 1,800. The rest have one of two slips:
* **Early slip:** an enemy-controller object (type 76, slot 3) is created one update apart around update 450–500.
  Its counter +0x98 differs by one step, and the RNG is one call apart by update 704. Both outcomes occur in the
  recording and in the playback, like a coin flip per game.
* **Late slip:** a graze (+10) or a kill is one update apart around update 1,070–1,078.

Ruled out so far:
* Full-RAM snapshots at the first update (0x00200000–0x00500000 and the hook area) show no word whose difference
  matches the early slip, except leftovers in the effects pool after the bullets (0x00468340, 0x3C records).
  Clearing that pool did not help.
* The loader busy flag (0x00339D90) is identical per update in the recording and the playback, including in runs
  that slip.
* The graze sound path (0x001372B0) does not use the RNG. The late slip correlates with the recorded game having
  grazed (XTC's debug counters), but XTC's state is now reset at the start.

Next: find what decides the type-76 creation update (its creating call site), and check state outside main RAM
(scratchpad RAM at 0x70000000, IOP / sound) and any remaining per-vsync code that writes game state.

## Not covered yet

* Runs longer than one stage: stage loads, stage transitions, continues.
* 2P; Arcade and Arrange outside Practice; Noir's other stages.
* Storage: the test log is 196 bytes per update (the whole pad block). A save would store only changes. Held
  buttons and the auto-repeat flags change every few updates, and rank changes every update in Arcade (a delta
  of a few units), so roughly 3 to 6 bytes per update compressed. A 30-minute run (~108,000 updates) is then
  about 300–600 KB, a few percent of an 8 MB memory card.
* Memory card writes: the plan is separate files through the game's own libmc calls, written to a temporary file
  and then renamed, never touching the game's save, and stress-tested on PCSX2 card images.

## Tools

The test build and run scripts live in the session scratchpad (not committed): `rp/build.sh` / `rp/build3.sh`
(build the test ISO with `replay.c` and the three call sites: 0x00112B1C / 0x00112B28 → `replay_pad_entry`,
0x0012E5CC → `replay_update_entry`; `RP_FIRST_MODE 2` ignores game 1; `RP_SNAP_AT`, `RP_SNAP_FULL`,
`RP_REGIONS` for snapshots and region tests), `rp/exp3.sh` (Arcade) and `rp/expn.sh` (Noir), and the diff
scripts `snapdiff3.py` and `fulldiff.py`.

## Shipped: K62, a game starts clean (28 November)

`ps2/hooks/game_start.c` hooks the start of the update path (0x0012E5CC, `jal 0x00138CD0`). At the first update of
each game (MAIN_STATE 5, not attract) it does what the stage's item initialiser 0x00132640 does for items, and
resets our own carried-over state:
* every item slot's flags word, the drop bytes 0x00338E54/55/58/59/5C and the drop tables 0x00495120–0x0049513F
  (Practice's GAME START skips the initialiser, so the previous game's drop rotation and items still on screen at
  RETURN MENU carried into the next Practice game);
* `bl_enemy_reset()`: the boss bullet-cancel tracker;
* `xtc_reset()`: the XTC graze test's side phase, counters and glow.
`kuro_frame` clears the latch whenever MAIN_STATE is not 5. In a normal game all of this is already at its initial
value at the first update, so only Practice after RETURN MENU changes. In the replay test build the same hook calls
`replay_update` after the reset. Patch 31,010 bytes; SHA-256 94472dd3… (docs/HANDOFF_2026-11-25.md).
PCSX2 smoke test: the attract demo, and two Noir Practice games either side of RETURN MENU (RETURN MENU still goes
back to Noir's Practice menu). With the replay harness on the new hook, a Noir and an Arcade replay matched exactly
(Noir through update 1,800, Arcade through 1,500). Repository tests pass. Hardware check H19.

Not changed: a shot-button press just before the stage starts (ship select confirm) can arm the game's own 120-frame
double-press window (player +0x264/+0x265, handler 0x0013B3E4). Retail behaviour; it is only noted here.

## For the slowdown work: what counts refreshes, not updates

The emulated slowdown holds game updates while refreshes go on (`arcade_slowdown.c`). Three things the game logic
reads advance per refresh, so during a hold they keep running at full speed where the arcade board would slow down
with the game:
* the frame counter 0x00338CDC ($gp-28692), incremented by the vsync service 0x00113390. The weapon item's type
  cycle and item handling read it (and several draw paths: flashes, the rank gauge blink);
* the pad state block 0x00341FA0 (2 × 0x50), rebuilt per refresh by 0x0010DF40 / 0x0010DDF0, including the
  auto-repeat flags (+0x0C) and their timers, which the shot code reads directly (0x0010DD90 callers);
* Arcade rank creep (0x0012E478–0x0012E880) runs per loop pass with a timing-dependent step. Codex's
  `arcade_slowdown_rank_gate` already skips it while holding.
The replay test makes the frame counter count updates during a game (undo the vsync increment in the pad read, add
one per update) and stores the pad block per update; the same two changes would keep these in step with emulated
slowdown.

## For Codex

The open job is the Noir replay slips (above). Everything is test-only: never commit a build with `replay.c` in it.

**Tools** (`research/phase44/tools`). The shell scripts expect `RP_WORK` to be a work folder holding PCSX2
(`$RP_WORK/ext/pcsx2/build/bin/pcsx2-qt`), the retail ISO (`$RP_WORK/iso/Ibara (Japan).iso`), the BL ROM
(`$RP_WORK/blk/ibarablk.zip`), and folders `rp/` and `runs/`. `tomenu.sh` compares screenshots with a Mode Select
reference, `$RP_WORK/runs/t1.png` (not committed: take one at Mode Select, 340×480 as `ctl.sh shot` crops).
* `session.sh ISO` / `launch.sh` (Xvfb :50 + PCSX2), `ctl.sh key|down|up|shot` (xdotool input, screenshots).
* `build3.sh`: builds `$RP_WORK/rp/rp.iso` with `replay.c` and the two pad-read sites (0x00112B1C / 0x00112B28 →
  `replay_pad_entry`) plus `REPLAY_BUILD`, then restores the tree. Game 1 is ignored (`RP_FIRST_MODE 2`), game 2
  recorded, game 3 replayed. `SNAP=` sets the first snapshot update; `EXTRA=` adds defines (`\n#define
  RP_SNAP_FULL`, `RP_SNAP_LOW`, `RP_SNAP_WIDE`, `RP_BUSY_LOG`, `RP_REGIONS ...`). It writes the `rp` symbol to
  `$RP_WORK/rp/sym.txt`.
* `expn.sh TAG` (Noir Practice) and `exp3.sh TAG` (Arcade Practice): play the three games and print the checkpoint
  comparison (`updates compared N mismatches M`, first mismatches as (update, score, rank, scene<<24|tick, seed, x,
  y, bombs)). `LOOPS=2` for Noir (longer scripts die before the pause and break the menu navigation).
* `snapdiff3.py SAVE FIRST` (active objects and P1 per 50-update snapshot), `fulldiff.py`, `widediff.py`,
  `corr.py` / `corrlow.py` (words whose rec/play difference occurs exactly in the slipping runs).
Each Noir run takes about 5 minutes; batches of 4–6 in the background work well.

**Suggested next steps**
1. Early slip: find the call that creates the type-76 object in Noir stage 1 near update 450–500 (enemy slot 3,
   +0x98 counter one step apart) and what decides its update. Log that site's inputs per update in both runs.
2. Check state outside main RAM: scratchpad RAM (0x70000000) and anything the IOP / sound side feeds back.
3. Late slip: snapshot just before update 1,065 in a run that slips (`RP_SNAP_WIDE`; about 1 in 4 runs).
