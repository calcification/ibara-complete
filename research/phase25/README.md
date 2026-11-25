# Phase 25 — Stages 3–6 compared with Black Label; stage scripts

The method is `tools/stage_compare/run_stage.py` with the same conditions in both games:
* invincible P1, shot held, shot level 2;
* rank locked at 0x800000.

Black Label (MAME) is deterministic. The PS2 is not, because the boss attack choices are random and both games
draw different random numbers (phase 14). So only structure is compared: enemies, HP, attack types, timing.

## Overview per stage (2026-11-24)

| Stage | Enemies (types, counts, HP, score) | Bullets | Result |
|---|---|---|---|
| 1–2 | phases 14–15 | phases 14–15 | matched earlier (HP, fire timer, boss logic) |
| 3 | all 11 types equal; only subtype counters differ (logging artefact) | equal structure; boss (type 51, 46 parts) core destroyed at frame 11,456 in BL vs 11,352 on PS2 | **matches**. A first run showed 1.5× the boss bullets on PS2; a second run did not, so this is random attack choice. Small extras (type-50 pairs, type-21 escorts) follow how long their parents live. |
| 4 | equal except the spawned escorts of the mid-boss (type 41: BL 93 type-21 + 10 type-4, PS2 34 + 23) | mid-boss window 2,900–4,000 uses other bullet types; boss minion bursts differ | **matches** (2026-11-25): the mid-boss untouched has the same entry, attack and exit, and wanders randomly; the boss runs the same skeleton in every run, with a random choice of opening attack (below) |
| 5 | **type 52: BL 108, PS2 36** (9 waves vs 3); the rest equal (type 23 escorts follow the boss fight length) | BL fires far more in frames 1,500–4,500 (the extra type-52 waves) | **stage script difference; ported** (below) |
| 6 | equal through the stage-6 boss | equal up to ~16,000 | both games continue the same way: green form, rose form, cutscene, staff roll (record 17). The PS2 logger stops when its stage counter changes, which is why the PS2 log ends earlier. Open: BL's rose form spawns enemy type 79 (6,815) and lasts longer; the PS2 rose form isn't logged yet. |

## Stage scripts

Each stage runs a script of 16-bit words. The records are time-ordered `(time, type, position, subtype, flags)`,
interleaved with commands `0xFFxx` that take arguments, and sub-scripts reached through pointer tables.

* BL keeps the six scripts in RAM at `0C200320`, `0C200F92`, `0C201214`, `0C201B5C`, `0C202142` and `0C2035FC`,
  big-endian. The spawn command handler is `0C08CA10`, and the script pointer lives at `0C2ABAA4`. These were
  found with `bl_spawn_pc.lua`, a write tap on enemy type 52 that logs PC, PR and the script pointer.
* The PS2 executable keeps them at `0x001EB048`, `0x001EBD3A`, `0x001EC004`, `0x001EC99C`, `0x001ECFC0` and
  `0x001EE4F0`, little-endian. Each is preceded by PS2-only `FF10` preload commands. Stage 5's table word
  `0x001F1850` points to its start, `0x001ECF80`.

`compare_scripts.py` takes a BL RAM dump (`bl_dump_ram.lua`) and the retail executable, then diffs the six scripts
word by word. After layout noise is removed (alignment zeros, pointer values, PS2-only `FF2A`/`FF27` commands), the
results per stage are:

| Stage | Difference | Status |
|---|---|---|
| 1 | `FF0F 0001` (music) argument 0x0C (BL) vs 0x10 (PS2) | left (music handling) |
| 3 | none; the reported block is BL's eight 15-word sub-scripts, which the PS2 also has, padded to 32 bytes | — |
| 4 | the PS2 has an extra `FF0C 0033` | left (PS2 addition) |
| 5 | BL has **six more type-52 records** after the third: times 0x348, 0x4B8, 0x578, 0x7A8 ×2 and 0x898. BL also has one 12-word block at `0C2025A0` that nothing references (dead data). | **ported** |
| 6 | BL has an extra `FF0C 004A` at the start (preloads graphics set 0x4A). The "different end" is the opening scene's script, stored right after stage 6 (see "Script commands identified"). | graphics preload; the opening only differs in music handling |

### Stage-5 waves (ported)

The PS2 script can't grow in place. Instead, `bl_scripts_build` (`ps2/hooks/bl_enemy.c`) builds a copy when Noir is
entered:
* it copies the retail words up to the end command `FF03 7FFF`;
* it inserts BL's six records after the third wave;
* the runtime table then points `0x001F1850` at the copy.

The BLACK LABEL test build instead builds the copy on its first gameplay frame. If the retail words aren't the
expected ones, the copy is the plain retail script. Only the six records (30 numbers) are in the repository.

Check (K44): after the change, the stage-5 run gives **108 type-52 spawns on PS2 against BL's 108**, with the same HP
and score distribution. The bullets in frames 1,500–4,500 are at BL's level. On the release disc, entering Noir sets
`bl_s5_ready` and `0x001F1850` points to the copy.

## Stage 4 mid-boss, untouched (2026-11-25)

`run_stage.py --stage 4 --boss-type 41 --noshot` keeps the mid-boss's parts at full HP in both games:

* **Entry path:** identical to the pixel for the first 650 frames.
* **Movement after that:** it wanders between different points. The type-41 handler (`0C091A00`) calls the random
  routine `0C062780` three times, and the two games draw different random numbers (phase 14), so this is not a rule
  difference.
* **Attack:** the same type-14 + type-1 ring, at about 280 (BL) vs 290 (PS2) bullets per 500 frames.
* **Exit:** at the same time.

**The mid-boss matches.** The escort and bullet differences in the shooting runs came from kill timing.

The no-shot mode now also covers parts that receive their HP a frame after they appear
(`bl_stage_log.lua` / `spawnlog.c` `BL_NOSHOT`). The stage-4 boss's parts were unprotected before this.

## Script commands identified

The interpreter is `0C071DB0`. After the time word comes either an enemy type (< 0xFF00), spawned through the
per-type table `0C1756B0` (type 52 → `0C08CA10`), or a command 0xFFxx, run through the table `0C175610`.

| Command | Meaning (BL handler) |
|---|---|
| `FF0C n` | load graphics set n: requests every resource in list n of `0C1DD458` (`0C069710`); the script waits until they are loaded (`0C072B30`) |
| `FF0F a b` | music: the stage tracks, 8 = boss, 9 = stage-6 boss, 0x0C = staff roll (so the stage-1 difference, 0x0C vs 0x10, is the track) |
| `FF26` | sound driver command `0C060078(0, 16)` (fade) and clears `0C3CA6F4` |
| `FF1E n` | used inside the boss scene scripts (table `0x001F1C40` on PS2, `0C206540` in BL) |

The stage list is BL `0C2065A0` and PS2 `0x001F1CB0`: entry 0 is the opening, entries 1–6 the stages, then the
ending. Its first entry starts right after the stage-6 script, so the "stage-6 end" difference above is really the
**opening**: BL fades the music with `FF26` where the PS2 runs `FF0A`. BL's extra `FF0C 004A` at the start of stage 6
preloads graphics set 0x4A.

## Stage 4 boss (2026-11-25)

The no-shot mode cannot hold this boss: its main parts keep HP 0, so the health lives elsewhere. Instead, its bullets
per 250 frames from its arrival were compared across one BL run and three PS2 runs:

* **Skeleton, every run:** an opening attack, a type-6 burst of about 600 bullets, then alternating type-14 and
  type-0 phases. The boss dies at about the same time in all runs.
* **Opening attack:** type 13 in BL. On PS2 it was type 3 in two runs and type 13 in one.

The type-58 handler (`0C0A6A70`) calls the random routine (`0C0A72C2`), so the opening attack is a random choice.
**The boss matches.**

## Stage order, playlists and after stage 6 (2026-11-25)

The stage-list index ("stage record") is BL `0C23E0A6`, PS2 `$gp-28248`. Each record names a script:

| Records | Content (both games) |
|---|---|
| 0 | opening |
| 1, 3, 4, 2, 5, 6 | stages 1–6, in that order. The script "markers" used above are `FF0F` music commands, so the labels by music number were: music 3 = stage 2, music 4 = stage 3, music 2 = stage 4. The stage-4 extra `FF0C 0033` on PS2 therefore belongs to stage 3. |
| 7, 8, 9 | the mode playlists: `FF02 n` = play record n. 7 runs 0, 1, 3, 4, 2, 5, 6, then `FF01`; 8 does the same after an `FF12`; 9 plays the loop twice |
| 10–16 | the post-stage-6 scenes: the type-78 controller started by `FF01`, then the cutscene. All end with `FF02 0011`. |
| 17 | staff roll (music 0x0C), then name entry (record 11) |

* **Game start:** BL picks the playlist as table `0C173A94` = 7, 8, 9, 11, indexed by a mode byte that BL leaves at 0,
  so it always plays record 7, the single loop. The PS2 does the same (`0x001CE68C`, table `0x00338970`), indexed by
  the menu choice: NORMAL = 7, HARDER = 8, EXTENDED = 9 (two loops).
* **After stage 6:** both pick the next record from the same table (BL `0C06BD80` / PS2 `0x0013C138`, table
  0, 13, 14, 15 by which players are alive): cutscene, then staff roll.
* **Correction:** the "extra boss after stage 6" in the first overview was the logger stopping early on PS2. Both
  games run boss → green form → rose form → cutscene → staff roll. The MAME trace is `bl_scene_trace.lua`; the PS2
  screenshots were taken in a full run.

## Stage-6 rose form (2026-11-25)

**Logger limits found first.** The PS2 logger keeps at most 2,600 spawns and 7,000 bullets. Stage 6 fills both, so the
earlier PS2 stage-6 logs simply stop at frame ~16,000. The test define `BL_COUNTS` (`ps2/hooks/spawnlog.c`) adds
uncapped totals at EE `0x01F5C000`: per enemy type, the count and the first and last frame; new bullets per 500
frames and type. MAME runs can stop shooting at a given stage frame with `SHOTOFF=N` (`bl_stage_log.lua`).

**Full stage 6, BL vs PS2 (shot level 2, rank 0x800000, invincible, shot held).** Everything up to the boss matches:
types, counts and bullets per bin. The boss is type 74 (103 parts). Its first core (subtype 0, 359 HP) dies at
about the same time in both, after ≈7,800 frames. Then the rose form:

| | BL | PS2 (two runs) |
|---|---|---|
| rose core (type 74 subtype 2, 300 000 points) HP | 430 | 430 |
| rose core killed after | 6,876 frames | 4,956 frames |
| roses (type 79, HP 2 in both; PS2 table `0x00225330`) | 6,815 at 1.10 per frame | 3,455 / 3,875 at 0.98 / 0.91 per frame |
| bullets during the roses, per 500 frames | ≈700 (types 14 and 0) | ≈280 (type 0) |
| end-of-stage controller (type 78) | frame 26,619 | 23,296 / 24,874 |

* **Damage-driven.** With the shot released at the start of the rose form (`SHOTOFF=19100`), BL's roses kept coming
  until frame 37,686 (≈18,500 frames) and only then ended. So the phase ends when the rose core is destroyed, with a
  long fallback timer.
* **No invulnerable windows.** The rose core's HP falls steadily in both games; BL's rate is about 0.68× the PS2's.
  The first form shows that the player's damage itself matches.
* **Most likely cause.** The roses absorb most of the shots: about 6,800 × 2 HP against the core's 430. So the
  core only receives what is left over, and BL's ≈15 % faster rose spawning, plus its denser type-14 barrage, is
  enough to stretch the phase. The rose logic is in the type-74 handler (BL `0C0A3800`, 4,315 instructions, not
  paired with the arcade by phase 11; PS2 `0x00173790`). Type 79 itself differs from the arcade by operands only.
* **Type 77** (13 objects) appears only in the BL log because BL's stage byte does not change during the cutscene;
  it is not stage content.

**Next for this phase:** find the rose spawn timer and the type-14 barrage in BL `0C0A3800`, against PS2 `0x00173790`
(for example a write tap on the enemy pool for type 79 spawns, as `bl_spawn_pc.lua` does for type 52). The HP-write
tap on the rose core caught nothing: the store probably isn't the 16-bit write the tap expected, so check the store
width first.

## Next

1. **Stage-6 rose form:** measured (above). BL's rose core lasts ≈40 % longer, with the same HP; next is the rose
   spawn timer and type-14 barrage in the type-74 handler.
2. ~~Mode choice in Noir~~ **done (K45):** Noir's GAME START confirms NORMAL at once (`0x001CAAE8`: GAME START branches into the submenu's confirm path in the same frame, so the cursor is row 0 = NORMAL and the press picks player 1; a first version that confirmed a frame later started player-2 games), so Noir always plays record 7, BL's single loop. Arcade keeps its choice.

## Reproduce

```
python3 tools/stage_compare/run_stage.py --stage N --out runs/sN --retail-iso 'Ibara (Japan).iso' \
    --pcsx2-dir PCSX2/bin --mame mame --bl-roms ROMS --shot-level 2 [--boss-type T [--noshot]]
OUT=blram.bin mame ibarablk -rompath ROMS -video none -sound none -nothrottle \
    -autoboot_script research/phase25/bl_dump_ram.lua
python3 research/phase25/compare_scripts.py blram.bin SLPM_663.01
OUT=spawn52.txt STAGE=6 TYPE=52 mame ibarablk -rompath ROMS -video none -sound none -nothrottle -nodrc \
    -autoboot_script research/phase25/bl_spawn_pc.lua
```
