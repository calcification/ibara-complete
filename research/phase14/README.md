# Phase 14 — Black Label stage content vs PS2 Arcade, enemy by enemy

**Method.** Both games are logged playing stage 1 with an invincible player holding shot:
* BL: `research/phase13/spawn_log.lua` in MAME (writes BL's invincibility byte `+0x288` each frame).
* PS2: test bake `--define BL_SPAWN_LOG` (`ps2/hooks/spawnlog.c`) of the BLACK LABEL build, Arcade game; keeps
  P1 invincible (`+0x27A`) and logs every new enemy part of the PS2 pool to `0x01F20000`, read from a savestate.
Each record: frame, slot, type (`+04`), subtype (`+08`), HP (`+3C`), score (`+40`), x, y. `compare_spawns.py`
aligns both logs at the first type-54 spawn and compares per enemy type over BL's stage-1 span.

**PS2 enemy system (static, 2026-11-20).** Pool `0x0045A840`, 192 × `0xB4` (arcade layout: x/y `+0x24/+0x28`,
HP `+0x3C`). Update loop `0x00128500` calls `table[type](part)`, table **`0x00205BF0`** (90 entries; e.g.
type 13 → `0x00196A70`, types 9/12 → `0x0018D3B0`, 18/19 → `0x0018E9A0`, 54 → `0x001624C0`). The PS2 port
keeps the arcade's enemy type numbering: BL's and PS2's logs use the same type numbers in the same order.

## Stage 1 results (`stage1_bl_vs_ps2_normal.txt`, `stage1_bl_vs_ps2_harder.txt`)

* **Same layout.** Every type appears in the same order and nearly the same counts; PS2 runs ~62 frames ahead
  throughout BL's 7,143-frame stage 1 (543 BL vs 517 PS2 spawns).
* ~~Subtype data differs~~ **Correction (same day): not a BL difference.** The subtype is also the enemy's own
  state counter (enemy routines do `subtype += 8/16`, e.g. `0x0018DD10`, `0x00196E88`). In BL too a type-13
  plane goes `0 → 0x10 → 0x11` over its first frames (`research/phase13/subtype_history.lua`); the PS2 logger
  first sees each part one update later than the MAME logger. Subtypes therefore match.
* **Spawn spacing differs slightly** (type 13: BL every 50 frames per pair vs PS2 47; type 15: 57 vs 53).
* **HP scales with mode/rank** (PS2 HARDER > NORMAL > BL's run), so HP differences are not a fixed BL table.
* **Boss phase** (types 55, 8) spawns more in BL; likely fight length, to be measured with equal damage.

**Conclusion so far:** BL stage 1 places the same enemies as PS2 Arcade; its differences must be in what those
enemies *do* (the ~288 changed enemy routines: bullets, movement, timing) and in HP/rank scaling.

**Next:** log enemy *bullets* per enemy type (count, speed, angle) in both games to find which types behave
differently, then port those routines. (Earlier idea: locate PS2's stage-1 spawn script (where type/subtype/time come from; the allocator `0x00127F80` has
181 callers) and rewrite its subtype values and timings to BL's, then re-log and diff to zero — not needed for stage 1.)

## Enemy bullets, stage 1 (`compare_bullets.py`)

Loggers: `research/phase13/bullet_log.lua` (BL; speed measured 6 frames after spawn, after the spawn flash) and
the bullet part of `ps2/hooks/spawnlog.c` (PS2, `0x01F40000`). Optional rank lock in both
(`RANKLOCK=` env in MAME, `--define BL_SPAWN_RANK=0x00800000u` on PS2) removes rank as a variable.

`stage1_bullets_rank800000.txt` (both at stored rank 0x800000):
* Same bullet types (0, 1, 2, 4, 11, 12) in the same sections, BL speeds 1.0–1.4 px/frame.
* **BL fires fewer** mid-stage: ~55–60% of PS2's type-0 bullets in frames 1,000–3,000; 8 vs 24 around 3,500.
* **Boss timing differs:** BL's boss burst is at 6,000–6,500 and the stage ends by ~7,000; PS2's burst is at
  6,500–7,000 and the fight runs past 8,500 (PS2 boss parts also had more HP at spawn).
* Caveat: equal stored rank may not mean equal difficulty if BL changed its rank scaling; check by reading
  how BL's enemy routines use rank (e.g. the type-0 shooters) before porting fire rates.

**Next:** (1) compare the stage-1 boss (type 5 parts): HP at equal rank and its attack sequence; (2) for the
mid-stage shooters, read BL vs arcade/PS2 code for fire-rate formulas (Phase 11 changed set ∩ types active there)
and port the formula changes as BLACK LABEL build patches; re-run both loggers until the timelines match.

## Enemy HP: ported (K11)

BL `0C0A9AE0` (pair of arcade `0C0A1530`, PS2 `0x00126C10`): **HP = base + base × stage / 16**, stage = BL's stage
byte (2 at stage 1), no rank term. PS2 Arcade uses `base + base × ((2^24 − rank) >> 16) >> 7` (≈ 2 × base at
rank 0x800000, which is why PS2 parts had about twice BL's HP). PS2 Arrange already has the stage form but reads a
stage *id* (`$gp-28248`: 1 at stage 1, 3 at stage 2, 4 at stage 3); the scene counter `$gp-28244` (`0x00338E9C`)
is 2, 3, 4 … at stages 1, 2, 3 = BL's byte. The BLACK LABEL build sends Arcade down that path reading the counter.

Result (`stage1_bl_vs_ps2_hpfix.txt`, `stage1_bullets_rank800000_hpfix.txt`, both at rank 0x800000): every type's
HP distribution now equals BL's; enemy bullets in BL's stage-1 span 1,119 (BL 1,081; before 1,839). What is left:
* **Boss sequence:** BL fires 316 bullets at 5,500–6,500 (types 0, 4, 2) and spawns 18 type-55 parts; patched PS2
  fires 98 there and 238 at 6,500–8,000, with 6 type-55 parts.
* **Mid-stage:** PS2 still fires ~1.5× BL's type-0 bullets at 1,000–2,000 and 2× at 2,500–3,000.

## Stage-1 boss after K11 (boss sampler: `COUT=` in `bullet_log.lua`, `CORE_LOG` 0x01F60000 in `spawnlog.c`)

Every 4 frames both loggers record the type-5 parts with subtype < 3 (core worth 100,000 and its two side parts):
HP and position. Rank 0x800000, player holding shot without moving (both games start the player at x 66, y 480).
* The side parts **share the core's HP**; core and part flags change at the same moments in both games
  (`C0008014 → C0008004 → C0008104 → D3008104`, last one = fight starts), and the core has 168 HP in both.
* **Correction (16-frame resolution):** the boss's sideways path is the same in both games (y 431–592, same
  speed and period); only its small forward/back wobble (x 238–282) runs in the opposite phase. (The 100-frame
  table had suggested different centres; that was sampling.) The PS2 core still takes damage more slowly at the
  sweep's far end and dies at 7,270 vs BL 6,728 although the PS2 player is at a *higher* shot level (3 vs BL's 2,
  both with the MG option): the difference is on the player side (shot/option reach), not the boss.
* BL's type-5 handler is **`0C0995B0`** (enemy type table `0C1DD6DC`, found by matching Phase 12 pairs against a
  RAM dump; 90 entries like PS2's `0x00205BF0`). It dispatches on the part's subtype (0..0x67) through a jump
  table; arcade `0C088C40` / PS2 `0x00165A10` is the same routine compiled as one function, which is why Phase 11
  listed it as a_only/b_only.

### Untouched boss (no shooting, rank 0x800000): attack timeline

`NOSHOT=1` in `bullet_log.lua`; the PS2 test player simply does not hold shot. BL is deterministic (a run with the
coin 61 frames later gives an identical timeline), so differences below are logic, not chance.

| frames (from first type-54) | BL | PS2 |
|---|---|---|
| 4,800–6,200 | type-4 barrage only, ~92 / 200 frames | same barrage plus extra type-0 shots (4,800–5,400), thinner after 5,600 |
| 6,800–7,200 | spiral, **4 arms** (556 bullets) | spiral, **2 arms** (282) |
| 7,200–7,600 | type-12 shots | same |
| 8,200–8,600 | spiral, **2 arms** (275) | spiral, **4 arms** (705) |
| 9,600–10,000 | no spiral (single aimed shots) | spiral, 4 arms (532) |
| 10,000–11,000 | types 1 + 12 | same |
| 11,000–11,400 | spiral, 2 arms (282) | spiral, 2–3 arms (484) |

So BL keeps the boss's attack skeleton and changes **which spiral variant runs at each step** (and drops one).
The spiral is a two/four-armed rotating ring, 1.0–1.25 px/frame, ~11° between bullets, from the core.

BL code that writes the spiral bullets (MAME write tap on the bullet pool, `research/phase13/bullet_pc_trace.lua`,
needs `-nodrc`): stores at `0C0BA524`/`0C0BA52E` (callers' return addresses `0C0BA4F6`, `0C0BA52A`) and
`0C0B9E20` (return `0C0B9F08`); the barrage uses `0C062780`/`0C0BAC32` (return `0C0BAC2C`) and `0C0B9E20`
(return `0C0B9C0C`); type-12 shots `0C0BB088` (returns `0C0BB0EA`, `0C0BB006`) and `0C0BB992` (return `0C0BBE00`).

**Next for the boss:** walk up from `0C0BA4F6` to the step that chooses the spiral variant (BL type-5 handler
`0C0995B0`, jump table `0C0995F0`), find the same step in PS2 `0x00165A10`, and patch the PS2 choice/sequence to
BL's; re-run the no-shot logs until the table above matches. Then compare the player's shot/option reach
(why the PS2 player at level 3 damages the boss less than BL's at level 2).

### Why the spiral order differs: random choice (no port needed)

All boss parts' flags follow the same timeline in both games except the spiral turrets (subtypes `0x50`–`0x55`).
They are not spawned: when the boss enters mode 3 (`+0x9A`, cycle 2 → 3 → 4 every 480 frames, identical in both
games), each turret part switches its subtype to `table[random(3)]` (BL `0C09A692`: call `0C062780` with 3, table
`0C1C7260` = 0x50, 0x52, 0x54; found with `research/phase13/emitter_subtype_tap.lua`). PS2 has the same table at
`0x0022F378` and calls its random function `0x00110FE0` in the same routine. So 4-arm vs 2-arm volleys come from the
random sequence, which differs between the two games; BL is repeatable only because its sequence restarts the same
way each game.

### Enemy fire timer: ported (K12)

BL changed the shared fire timer (arcade `0C0A9E40` → BL `0C0BC1B0`, PS2 `0x00122120`): before the usual
`base + factor × (rank >> 16) / 256` it lowers rank by stage × ((k << 18) + 0x40000), floored at 0 (k = settings byte
`0C234C04`, 3 by default), so enemies fire faster from stage to stage. Ported as `ps2/hooks/bl_enemy.c`. With both games'
turrets reading the same inputs, their counters now cycle identically (`turret_log.lua` / `BL_CORE_TURRET`).
Mid-stage, untouched enemies: BL 1,052 bullets in frames 0–3,600, PS2 955 before and 1,112 after; the shooters pass
the same timer arguments (90, 10) in both games, so the remaining mid-stage gap in *shooting* runs comes from
the player killing enemies faster in BL (as with the boss), i.e. player shot/option damage, not enemy code.

**Stage 1 status:** placement, HP, fire timing and boss logic match BL. Open: player-side damage/reach (BL's level-2
shot kills faster than PS2's level-3), then stage 2.

### Player damage and bullet speeds (stage 1)

* **Damage:** with shot level locked to 2 in both games, the boss core loses ~14–15 HP / 100 frames in BL and ~13
  on PS2 while in the line of fire, and both pause at the same phase change. The earlier gap came from the PS2
  player's different shot level (item drops) and the boss's random sweep direction. Nothing to port.
* **Bullet speeds:** the PS2 logger now measures velocity over 6 frames like the MAME logger
  (`tools/stage_compare`); per 500-frame bin the mean speeds match (1.00/1.10/1.04/1.24 vs 1.00/1.09/1.00/1.25).

Stage 1 enemy content is therefore matched at fixed rank. The comparison now runs as one command per stage:
`tools/stage_compare/run_stage.py`.
