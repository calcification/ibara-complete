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
| 4 | equal except the spawned escorts of the mid-boss (type 41: BL 93 type-21 + 10 type-4, PS2 34 + 23) | mid-boss window 2,900–4,000 uses other bullet types; the boss (type 58) minion bursts (type 43) come in two waves in BL, one longer wave on PS2 | **open**: mid-boss and boss timelines need the untouched (no-shot) comparison |
| 5 | **type 52: BL 108, PS2 36** (9 waves vs 3); the rest equal (type 23 escorts follow the boss fight length) | BL fires far more in frames 1,500–4,500 (the extra type-52 waves) | **stage script difference; ported** (below) |
| 6 | equal up to the final boss | equal up to ~16,000 | after the stage-6 boss, BL keeps going for ~12,500 frames with enemy types 77, 78, 79 and 60 (a further boss); the PS2 stage ends. See "Stage scripts". |

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
| 1 | header `FF0F 0001` argument 0x0C (BL) vs 0x10 (PS2), probably the music track | left |
| 3 | none; the reported block is BL's eight 15-word sub-scripts, which the PS2 also has, padded to 32 bytes | — |
| 4 | the PS2 has an extra `FF0C 0033` | left (PS2 addition) |
| 5 | BL has **six more type-52 records** after the third: times 0x348, 0x4B8, 0x578, 0x7A8 ×2 and 0x898. BL also has one 12-word block at `0C2025A0` that nothing references (dead data). | **ported** |
| 6 | BL has an extra `FF0C 004A` at the start, and a different end (`FF05 0080 0001 FF04 003C 0000 FF26`, then a further script tagged `FF0F 0001 0001`). This is where BL continues into the extra boss. | open, belongs to game flow (G1–G3) |

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

## Next

1. **Stage 4**: run the mid-boss (type 41) and boss (type 58) with `--noshot --boss-type N`, compare the untouched
   timelines, and find the step that differs.
2. **After stage 6**: work out what BL's `FF26` and the `FF0F 0001 0001` script do, and whether the PS2 Arcade code
   has that boss (types 77–79; on PS2 probably the second-loop final boss). This is part of game flow G1–G3.
3. The `FF0C` command (stage 4 PS2 `0x33`, stage 6 BL `0x4A`): identify what it loads.

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
