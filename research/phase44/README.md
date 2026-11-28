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
| Start state: item drop state. The stage's item initialiser 0x00132640 zeroes the bytes 0x00338E54/55/58/59/5C and the tables 0x00495120–0x0049513F; Practice's GAME START skips it. | Drop counter 3 vs 0 at the first update; restoring that one byte alone made things worse, because the tables still differed. | Zero all of them at the first update (both runs). |
| Rank set at game init: 0x00338EB8 += rand(2), drawn before the first update. | 0x10 vs 0x11. | Store and restore 0x00338EAC–0x00338EBB. |
| Our XTC graze test (xtc.c) checks one side per update, alternating, and kept its phase from the previous game. | +10 graze one update apart (update 1078). | `xtc_reset()` at the first update. |
| Our boss-cancel tracker (bl_enemy.c `bc_hp`, `bc_left`) persists between games. | (Found by reading; it could clear bullets at the start.) | `bl_enemy_reset()` at the first update (only built with `REPLAY_BUILD` for now). |

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
