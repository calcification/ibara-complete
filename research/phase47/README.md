# Phase 47: replays for release — Ibara Full Bloom v1.0 (Claude, 28 November 2026)

Release name and version: `ps2/include/version.h` (`IFB_NAME` "Ibara Full Bloom", `IFB_VERSION` "1.0").

## K63: every game is recorded (`ps2/hooks/rpl.c`)

Method from phase 44 (and Codex's phase 45), in a compact form for saving:
* hooks: the game-update hook of K62 (0x0012E5CC → `game_update` → `rpl_update`) and both pad reads of
  0x00112A80 (0x00112B1C / 0x00112B28 → `rpl_pad_entry`);
* per update: the pad block words the game reads through its accessors (0x00341FA0 + port × 0x50: +0 current,
  +8 pressed, +0x0C auto-repeat; values fit 16 bits), both players' button words (+0x24C … +0x254), and the rank
  change since the previous update;
* the frame counter 0x00338CDC counts updates during a game (vsync increment undone in the pad read, +1 per update);
* start state in the header: seed, frame counter, spawn counters (0x00338E4C–0x00338E53), rank state
  (0x00338EAC–0x00338EBB), both player records; the start-of-game reset (game_start.c) now also clears shots,
  bullets, and inactive enemy and effect slots, so a recording and its playback start from the same baseline.

File (in RAM at 0x01700000, up to 7 MB): `struct rpl_head` (magic "IBFB", Adler-32 checksum, version 0x0100,
stream length, update count, mode, stage, end state), then the stream: a byte 0x00–0x7F repeats the previous update
n + 1 times; 0x80 is followed by a 3-byte mask of changed 16-bit fields (18 fields) and their new values.

### Results (PCSX2, test build `RPL_TEST`: game 1 ignored, game 2 recorded, game 3 played back)

| Mode | Updates | Bytes per update | Checkpoints (every 30 updates) | End state (score, seed, stage tick) |
|---|---:|---:|---|---|
| Arcade Practice stage 1 | 1,778 | 3.10 | 60 / 60 match | match |
| Noir Practice stage 1 | 1,824 | 1.80 | diverges at update 870 (seed; same score) | — |

A 30-minute run is about 108,000 updates, so roughly 200–350 KB. Noir's divergence is the known stage-1 asset
timing (Codex, phase 45); its playback hold is not in the release recorder yet.

Release smoke test (PCSX2): attract demo, a Noir Practice game, RETURN MENU. Behaviour changes in normal play:
the frame counter (weapon item cycling and some flashes) now advances per game update, not per vsync, and unused
object slots are cleared at a game's first update.

## Next

1. The end-of-run prompt ("リプレイをセーブしますか？", size in KB) in the game's own memory-card dialog
   (panel 0x001CE830, text 0x001CEC40; message records like 0x002A9948), then saving with mcfile.c to
   `BISLPM-66301R<date>`.
2. A REPLAY entry listing replay saves; playback with the mode and "Ibara Full Bloom v1.0" drawn over the game.
3. Noir: bring Codex's asset-readiness hold into the release player.
