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

## K65: REPLAY in each mode's menu, and playback (`ps2/hooks/replaymenu.c`, `rpl.c`)

* Menus: ARCADE / NOIR MODE (frontend state 2) and ARRANGE MODE (state 9) get a fifth row, REPLAY, above EXIT.
  Arcade / Noir: labels and help from `rm_label` / `rm_help` (rows 0–2 copied from the game's tables every frame,
  so KURO's runtime help word still applies), row count, wraps and the EXIT compare patched
  (`REPLAY_MENU_PATCHES`). Arrange: label row 3 REPLAY, row 4 EXIT (the spare word 0x002A9058), its row patches
  raised to 5 and its help from `rm_arr_desc` (`PRACTICE_MODE_PATCHES_REPLAY`; the standalone BLACK LABEL build
  keeps 4 rows). The menus' own accept code ignores row 3; `rm_frame` answers it.
* The list: the game's memory card dialog look (panel 0x001CE830, text 0x001CEC40) drawn before the frontend
  frame's flush (0x001CA294 → `rm_flush`); the menus' pad reads (0x001C9438–0x001C9464) see nothing while it is up.
  It lists `BISLPM-66301R<mode letter>*` (sceMcGetDir 0x00155748, added to mcfile.c) newest first, as
  "ＹＹ／ＭＭ／ＤＤ　ｈｈ：ｍｍ　ＳＴｎ　score" (the date from the save's name, stage and score from each file's
  header); up / down move, shot plays, bomb goes back. Messages: checking the card, no replays, no card, load failed.
* Starting: the file is loaded into the replay buffer and checked (checksum, supported format); the player's Arcade
  options and FIGHTER TYPE are kept and the recording's applied (restored when the playback ends). The menus are
  then driven as a player would: GAME START confirmed (one injected press on port 0 through the menus' pad reads),
  and in Arcade's NORMAL / HARDER / EXTENDED submenu (state 3) the recorded choice (0x00338F0C) confirmed. KURO's
  select screen confirms the recorded ships at once (`bl_select.c`).
* During playback: "REPLAY　<MODE>" on the HUD (the game's HUD text writer 0x00111460, called from the HUD pass in
  `frontend_rank_bar`); START on the controller ends it. A Start that the recording does not hold is the player's:
  the pad block is rebuilt from the controller every vsync and holds the recording only from an update's start.
* Ending (START, or the end of the recording): as the pause menu's RETURN MENU. The pause byte (0x00338F10) opens
  the main loop's pause-menu call, now a static site (0x0012E778 → `rpl_pause_menu`: KURO's `sel_menu`, or the
  retail menu, or 1 = RETURN MENU for a playback). The frontend then comes back to the mode's menu, cursor on
  REPLAY (not Mode Select). No save prompt after a playback.
* Save names carry the mode: `BISLPM-66301RA…` Arcade, `RR…` Arrange, `RN…` Noir.

PCSX2 (release build; the test card has the game's save with Tate on, so the screen was rotated):
* Arcade: run with inputs → game over → saved (8,567 bytes); ARCADE MODE → REPLAY lists it; play: the recording's
  2,809 updates matched to the end (score, seed, stage tick); back to ARCADE MODE on REPLAY; START mid-playback
  ends it; bomb closes the list.
* Noir: run saved (`RN…`); NOIR MODE → REPLAY lists only it; plays (ship select confirmed automatically).
* Arrange: run saved (`RR…`); ARRANGE MODE → REPLAY lists only it; plays.

## Next

1. Noir playback accuracy: bring Codex's stage-1 asset-readiness hold (phase 45) into the release player.
2. Arrange's own CONFIG values (PLAYER STOCK, BOMB STOCK, EXTEND, CONTINUE; options.c) and the rank / slowdown
   options into the replay header.
3. Practice and 2P runs (no end-of-run prompt yet for Practice).
4. Delete a replay from the list (the PS2 browser can already).

## Replay format 3 and Noir's target search cursor

The Noir target selector at 0x00137DA0 uses a shared round-robin cursor
at 0x00338B98. Playback restores the recorded cursor along with the seed
and player state. The [controlled PCSX2 comparison](../replay_late/POD_CONTACT.md)
isolated this field from the pod records themselves.

Format 3 appends two 32-bit words to the format 2 header. The first
stores the 16-bit cursor value and the second stores the initial stage
tick. The stream encoding and the header prefix used by the REPLAY
list are the same. A format 2 file keeps its original update indexing
and uses cursor 0 on playback. Its original cursor cannot be recovered
from the stream. The menu checks the actual loaded file length and
checksum before applying the saved settings.

A new normal Noir recording starts at the first Stage 1 update. The
opening and ship confirmation run before replay input starts. The
initial stage tick is restored at that boundary so the opening's
length cannot shift the replay. Practice, Arcade and Arrange keep
their existing entry point.

For a PCSX2 diagnostic, bake the release profile with RPL_TRACE. This
enables sampled checkpoints without replacing the recorder or replay
menu. The test-only rpl_test_finish flag can request game-over teardown
after the current recorded segment. Compare a state at the save prompt
with one after the REPLAY menu's playback returns.

    python3 research/phase47/report_replay.py record.p2s playback.p2s symbols.json

### PCSX2 release-menu verification

PCSX2 2.8.2 used the real save prompt, memory card, and Noir REPLAY
menu. The diagnostic kept the player alive for the longer runs and
requested native game-over teardown at the end of each recording.

| Saved recording | Playback result |
| --- | --- |
| Format 2, 3,109 updates | Loaded with cursor 0 and consumed the full stream. |
| Format 3, 3,150 updates | Played after another game. Restored cursor 17 from a live value of 93 and consumed the full stream. |
| Format 3, 9,233 updates, through Stage 2 | Restored cursor 17, consumed the full stream, and returned to REPLAY. The final stage and stage tick matched. |

All three runs had zero stream decode errors. Both format 3 runs first
showed an RNG mismatch at sampled update 720, while the score and stage
tick still matched. The short run differed at 81 of 105 checkpoints and
the long run at 284 of 308. Both ended with score and RNG mismatches.
Stage 2 was first observed at update 8100 in the recording and 8070 in
playback, with samples every 30 updates. The first mismatch was already
in Stage 1. The cause of that remaining mismatch is still unconfirmed.
