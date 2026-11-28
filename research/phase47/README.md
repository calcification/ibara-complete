# Phase 47: replays in the release build (Claude, 28 November 2026)

The project's release name is Ibara Full Bloom; nothing is released before 1.0. `ps2/include/version.h` holds the
name and version for text shown at release (e.g. over replay playback); that text waits until 1.0.

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

File (in RAM at 0x01700000, up to 7 MB): `struct rpl_head` (magic "IBFB", Adler-32 checksum, file format 1,
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

## K64: the end of a run offers to save its replay (`ps2/hooks/endrun.c`)

* Where: the main state machine (0x00113400) runs state 8 (game over / name entry, 0x0013D580) after every
  finished game; when it returns 0 the game goes to the logos (state 1) and the title. Observed sequences: Arcade
  game 5 → 8 → 1 → 2 → 3; attract the same with the attract flag (no prompt). The call at 0x00113610 now goes to
  `endrun_state8`. It also carries KURO's old runtime word for that site (KURO skips state 8: no retail ranking or
  autosave), so the site has one owner in every mode.
* When: the last game was recorded (not a playback), at least 600 updates, checksum valid, not attract.
* Look: the game's own memory card dialog (`0x001D05C0(message, cursor)`, the frontend's): message 11
  ("セーブしますか？", はい / いいえ with the rose cursor) with its two text lines pointed at "リプレイをセーブしますか？"
  and "（使用容量　ＮＮＮＫＢ）" while the prompt is up; then 14 (セーブしています), 15 (セーブが終了しました) or 17
  (セーブに失敗しました; "空き容量が不足しています。" when the space check refuses). Each prompt frame is built like the
  game's simple states: 0x00113390, 0x00112500, clear 0x001125B0(0), 0x00112A20, the dialog, 0x00112670(7, 7),
  present 0x001117D0. KURO first loads resource group 1 (`0x00129F00(1)`, the font and panel; state 8 loads it in
  the other modes) and waits for the loader.
* Buttons as the game's dialogs: left / right (0x04 / 0x08) move, shot or bomb (0x10 / 0x20) confirm.
* Size shown: replay file + icon + icon.sys, rounded up to KB, plus 3 KB for the folder entries.
* Saved as `BISLPM-66301R<YYMMDDhhmm>/REPLAY.DAT` (clock 0x0010C530, the console's local time), browser title
  "イバラ　リプレイ" / "<MODE>　ST<n>　<score>".

PCSX2 (release build):
* Arcade game over, unformatted card: prompt (39 KB for an 80-second run) → はい → セーブに失敗しました → logos.
* Arcade game over, card with the game's save: はい → saving → saved. On the card: `BISLPM-66301R2611281542`
  with icon.sys, icon and REPLAY.DAT (1,852 bytes, 2,503 updates, header and Adler-32 checksum valid); the file
  system is consistent; the game's save is untouched; title イバラ　リプレイ / ＡＲＣＡＤＥ　ＳＴ１　１５５２０.
* Noir game over: the font loads (NOW LOADING), prompt correct, いいえ → logos → title.
* Not covered yet: Practice runs (they leave through RETURN MENU / the practice menu, not state 8), 2P.

## Next

1. ~~The end-of-run prompt~~ done (K64). Practice and 2P runs next.
2. A REPLAY entry listing replay saves; playback with the mode drawn over the game (the name and version text
   at 1.0).
3. Noir: bring Codex's asset-readiness hold into the release player.
