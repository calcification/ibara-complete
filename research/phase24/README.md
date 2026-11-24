# Phase 24 — Rank on bombs, Hadou, shots and time (F8)

Question: which rank changes does Black Label make around bombs and Hadou, and does Noir match? Answering it turned
up four PS2 Arcade rank rules that BL does not have. Noir now drops them.

## Measurements

**BL (MAME).** `bl_rank_bomb.lua` taps writes to BL's stored rank `0C297A3C` and logs the writer PC, the caller
(PR), the delta and the new value. The setup is Stage 1, P1 straight A, invincible, shot held, 3 bombs, and rank held
at 0x600000 until the action (MODE `none` / `bomb` / `hadou`, the Hadou charged for 140 frames). The `NOSHOT=1`
run keeps the shot released.

* **No time creep and no cost per shot.** With shot held, rank stays flat between events for 600 frames. With shot
  released, the only steady writer is 0x1000 from enemy code (`0C0BBF10` / `0C0BC020`). The arcade original has
  that code too, and the PS2 counterparts are `0x001247A4` / `0x001248F8`.
* **Bombs make no rank call.** The trigger is `0C073600` (phase 18). A plain bomb's rank effect comes from the roses
  it creates: two level-0 roses gave +0x80000 each, through the rose handler `0C07E440`.
* **Hadou.** It produces no roses. It kills enemies, which drop level-1 medals (type 3, −0x20000 each, 18 of them)
  and type-11 items.
* **Rank writers.** All BL rank writes go through `0C071C90` (harder, floor 0) and `0C071CC0` (easier, capped). The
  easier one has a single caller, the rose handler. The harder one is called from the item handlers and from enemy
  code.

**BL item rules (disassembly).** The pickup dispatcher is `0C07E160`.

| Item type | BL handler | Rank change |
|---|---|---|
| 0 | `0C07CEC0` | harder 0x8000, only on a pickup at the maximum (after the score call `0C07D2E0`) |
| 1 (option) | `0C07D100` | harder 0x80000, at the maximum |
| 2 (fragment) | — | harder 0x40000 (done, K07) |
| 3 (medal) | — | harder level × 0x20000 (done, K09) |
| 4 | `0C07E250` | harder 0x80000, at the maximum |
| 6 | `0C07E350` | harder 0x400000, at the maximum |
| 7 (rose) | — | easier `table[level] << 11`; table `0C189C8C` = 0x100, 0x180, 0x300, 0x600, so +0x80000, +0xC0000, +0x180000, +0x300000 |

The rose row explains phase 13's "unexplained" +0x180000 writes.

**PS2 Noir before this phase (PCSX2).** This used a test build with `BL_SPAWN_LOG` and `BL_RANKLOG=0x600000u`
(`ps2/hooks/spawnlog.c`). It holds rank and three bombs until the first bomb, then logs every rank change as
(frame, old, new) at EE 0x01FD0000. The differences from BL:

* Rank got harder every frame, by 17 on one frame and 37 on the next. That came from two rules:
  * Arcade's time creep, which takes `$gp-28216` off rank each frame (`0x0012E490` path);
  * Arcade's rank per shot fired (`0x0013ADE4` harder(10 n), `0x0013B410` harder(16)).
* Roses used Arrange's `table << 10` with table 0x100–0x400, so +0x40000 for level 0, half of BL's amount.
* Every type-0/1/4/6 pickup made rank harder (4096 / 0x10000 / 0x10000 / 0x80000). A pickup at the maximum made
  no rank change at all.
* Arcade's bomb-use calls were already off in Noir (phase 18).

## Changes (Noir only, switched with the runtime table)

| Site | Change |
|---|---|
| `0x0012E488` `bnez` → `b` | takes Arrange's branch: no time creep, and the score caps at 999,999,999 as in BL (phase 13) |
| `0x0013ADE4`, `0x0013B410` | the per-shot `jal harder` calls become `nop` |
| `0x0012F6F4/8` → `bl_rose_rank` (`ps2/hooks/bl_player.c`); `0x0012F70C` `sll 10` → `sll 11` | BL's rose amounts |
| `0x0012FC4C`, `0x0012F064`, `0x0012FA90`, `0x0012F9B0` | the per-pickup Arcade `jal harder` calls become `nop` |
| `0x0012FC34`, `0x0012FA78`, `0x0012F998` | the mode tests fall through, so a pickup at the maximum gets Arrange's (= BL's) harder call |

Retail Arcade and Arrange are unchanged.

## Result (PCSX2, K43)

The same capture after the change, 2,300 frames after a bomb:

* rank changes only on events, with no per-frame drift;
* the event amounts are BL's: roses in multiples of 0x80000 / 0xC0000, fragments −0x40000, medals −0x20000 × level,
  and enemy code ±0x1000;
* the −0x1000 that came with a small-P pickup is gone.

## Open

* Hadou items. BL's Hadou yields medals and type-11 items, and its bullet cancel makes no roses. In the PS2 capture
  the held-bomb input produced rose pickups. Whether that was a Hadou, and what PS2 Noir's Hadou drops, belongs with
  the item and enemy comparison (G6 and onward).
* Type-11 items: not identified.

## Reproduce

```
OUT=bomb.txt MODE=bomb mame ibarablk -rompath ROMS -video none -sound none -nothrottle -nodrc \
    -autoboot_script research/phase24/bl_rank_bomb.lua        # MODE none|bomb|hadou, NOSHOT=1, RANK=hex, END
```

PS2: put `#define BL_SPAWN_LOG` and `#define BL_RANKLOG 0x600000u` at the top of `ps2/hooks/xtc.c` and
`spawnlog.c` (temporarily), then build with `scripts/build_black_label_iso.py` without `--bl-rom`, so there is no
select screen. Start Noir Normal, hold shot, and bomb. A savestate's EE RAM then holds the count at 0x01FD0000,
followed by 12-byte rows (frame since the bomb, old rank, new rank).
