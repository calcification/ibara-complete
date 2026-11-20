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
