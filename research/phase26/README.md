# Phase 26 — Arrange CONFIG: PLAYER STOCK, BOMB STOCK, EXTEND, CONTINUE

The user's request (25 Nov): give ARRANGE CONFIG Arcade's CONFIG rows except DIFFICULTY, with defaults that play
exactly like retail Arrange. Code: `ps2/hooks/options.c` (arrcfg_*, arr_rules_*), patch rows:
`scripts/build_ee_hooks.py` `ARRANGE_CONFIG_PATCHES`. All addresses are the retail executable's (gp = 0x0033FCF0).

## How retail Arrange plays

| Setting | Arcade | Retail Arrange |
|---|---|---|
| PLAYER STOCK | player set-up `0x0012D840` stores `$gp-28912` in the player's stock byte (+0x25A) | `0x0012D8E4 li a0,2` (stock byte 2, shown as "3" in the value names "1".."6") |
| BOMB STOCK (`$gp-28908`) | 0 none; 1 half (+20 fragments, +0x25E); n ≥ 2: +40 fragments (one bomb) and n − 2 more bombs (+0x25D) — routine `0x0012D520`, also run on each respawn | setting 0 none (`0x0012D5BC`, reads **Arcade's** byte); otherwise one bomb: `0x0012D5D4` sends Arrange to `0x0012D7CC` (+40) and `0x0012D7D8` skips the extra bombs |
| EXTEND (`$gp-28916`) | `0x0013E290` sets `$gp-28296` (first extend) and `$gp-28292` (every, 1e9 = none) from the tables `0x00213540` / `0x00213560`; it runs at settings load and on leaving CONFIG | first extend fixed 10,000,000 (`0x0012D8C0` → `0x0012D930`), then every 10,000,000: the extend check `0x0013ABD8` sends Arrange to its own copy at `0x0013AC40` with the fixed interval `0x0013AC54` (Codex's note on `codex/noir-logger-arrange` caught this) |
| CONTINUE (`$gp-28932`) | checks at `0x0012C594`, `0x0012C714`, `0x0012C924` | the Arrange flag (`$gp-28076`) checks right after them (`0x0012C5B4`, `0x0012C734`, `0x0012C934`) take the CONTINUE OFF path: game over (`0x0012CB5C`: `$gp-28232` = 480, `$gp-28272` = 1). The ON path sets the 1,200-frame countdown `$gp-28236`. Retail Arrange has no continue |

## What the new rows do

Values: PLAYER STOCK and BOMB STOCK index Arcade's value names (`0x002A9290`, `0x002A92B0`); EXTEND is 10M EVERY
(retail Arrange) or one of Arcade's seven; CONTINUE OFF / ON. Defaults: stock 2 ("3"), bomb "1", 10M EVERY, OFF —
retail Arrange with Arcade's default settings. (Retail Arrange's bomb rule reads Arcade's BOMB STOCK byte (0 = no
bomb); with the new rows Arrange's own value decides instead.)

`arr_rules_apply` runs at the start of the player set-up (`0x0012D840` → `j arr_rules_entry`; every game start,
practice start and join). For an Arrange game it rewrites:

* stock: `0x0012D8E4 li a0,<stock>`;
* bomb: `0x0012D5A0` / `0x0012D7FC lbu a1,$gp-28908` → `li a1,<bomb>`, `0x0012D5D4` → nop (half bomb as Arcade),
  `0x0012D7D8` → `b 0x0012D7FC` (extra bombs as Arcade) — Arcade's rule with Arrange's value;
* extend (not 10M EVERY): `$gp-28296` / `-28292` from Arcade's tables at the chosen value, `0x0012D8C0` and
  `0x0013ABD8` → nop (Arcade's first extend and interval);
* continue ON: the three `lbu …,$gp-28932` → `li …,1` and the three Arrange checks → nop.

Other games get the retail words back (and Arcade's extend values recomputed with `0x0013E290` when an Arrange
game had overridden them). The words are only rewritten, and the caches flushed, when the wanted set changes.

The menu (frontend state 10, `0x001CCC98`): label table `0x002A9060` → `arrcfg_label` (8 rows), row count 4 → 8 (draw
loop `0x001CCEBC`, cursor down `0x001CCFC8`, cursor-up wrap value `li v0,7` in the delay slot `0x001CCFB0`),
accept dispatcher KEY CONFIG / EXIT rows 2 / 3 → 6 / 7 (`0x001CD088`, `0x001CD098`), its "no handler" exit
through the unreachable word `0x001CD9AC` to `arrcfg_accept_entry` (Circle cycles rows 2-5), KEY CONFIG's return
row 2 → 6 (`0x001CA0A0`), value column `0x001CCE64`-`0x001CCE84` → `arrcfg_value(row)` (BULLET DESIGN included),
help table `0x002A9420` → `arrcfg_desc` (Arcade CONFIG's help lines for the new rows).
