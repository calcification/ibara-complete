# Phase 13 — Black Label behaviour oracle in MAME

**Why:** static reading of BL's SH-3 code (Phase 11) shows *where* BL differs but not always *what it does*.
MAME (0.264, Ubuntu package `mame`) runs the user's own `ibarablk` set; small Lua scripts drive inputs and
watch memory, so BL behaviour can be measured instead of guessed. No ROM data or MAME output is committed.

```bash
mame ibarablk -rompath <dir with ibarablk/> -video none -sound none -nothrottle -nodrc \
     -autoboot_script research/phase13/ship_readers.lua -skip_gameinfo      # SHIPVARIANT=A|B
mame ibarablk -rompath ... -video none -sound none -autoboot_script research/phase13/ship_tables.lua
```

* `list_ports.lua` — input port/field names (`:PORT_C` coin/start, `:PORT_D` P1 stick + buttons 1–4).
* `ship_readers.lua` — coin, Start, ship select (variant B presses Right), holds Button 1; a memory read tap
  on P1's ship byte `0C29D1DF` (low byte of the bus word) counts reading PCs. Needs `-nodrc` (the SH-3
  recompiler reads RAM directly) and the tap object kept in a global (Lua GC removes it otherwise).
* `ship_tables.lua` — dumps the per-ship tables found by the readers.

## Results (2026-11-20, `ibarablk` U4 `ee1f1f77`)

* 4,800 frames run in ~10 s (recompiler) / ~21 s (`-nodrc`). Variant A → ship byte `00` (Bond, straight, A);
  variant B (Right at the select) → `04` (**spread**).
* 25 exact readers of the ship byte; the `0C0B8xxx` ones are the BL-only select screen (`0C0B8210`).
  In play the byte indexes per-ship tables:

| reader | use | table | straight | spread |
|---|---|---|---|---|
| `0C073AD2` (`0C0739E0`) | `jsr` per-ship shot routine | `0C17E1FC` | `0C077030` (entries 0–3) | `0C077060` (4–7) |
| `0C06ED00`, `0C06EF84`, `0C06F26E`, `0C076F42`, `0C075A20` | ship × 8 → 2-word ship record | `0C17E12C` | 2nd word `0C175E14` | `0C175E18` |
| `0C06D22A` (`0C06D170`, player start) | per-ship 16.16 value, likely move speed | `0C1740D0` | 2.75 / 2.5 / 3.0 / 3.5 | 2.25 / 2.125 / 2.375 / 2.5 |
| `0C0779D2` | ship & 4 | `0C182834` | `0C18281C` | `0C182828` |
| `0C070674` | ship & 0xC | `0C174FF0` | — | — |
| `0C07113E` | (ship >> 2) & 1 for the XTC display | — | — | — |

**Port plan for F1/F5:** the BLACK LABEL build needs a ship-kind flag per player (BL encodes it in bit 2 of
the ship byte; the PS2 byte is side·4 + type), BL's spread shot routine `0C077060` and data `0C175E18`
translated to the PS2 shot system, the spread speeds, and a select step. Next: trace `0C077030` vs
`0C077060` and the tables they read, then map them onto PS2's shooter (`0x0013B2F0` / projectile writer
`0x0011A580`).

## Straight/spread = the arcade pilots' mechanics (2026-11-20)

* BL's per-ship, per-level shot tables (`0C17F388` → 8 × 7 patterns; pattern = shot count + 24-byte records,
  flags `C8000000`, angle, 16.16 offsets) were dumped with `dump_shot_patterns.lua` and compared, word for
  word, with the PS2 table at **`0x00212E50`** (same format, little-endian): **BL straight A–D = Bond A–D and
  BL spread A–D = Dyne A–D, 7/7 levels each** (both share one table for type B/C of the second set).
* BL's per-ship speeds (`0C1740D0`: 2.75/2.5/3.0/3.5, 2.25/2.125/2.375/2.5) are the PS2 table at
  **`0x00205F50`**, Bond then Dyne.
* So BL indexes the arcade mechanics by ship-kind·4 + type instead of side·4 + type: the pilot is cosmetic and
  straight/spread picks the shot set and speed. The PS2 data already holds both sets; nothing new to port for
  shots or speeds. A BL-faithful select only needs the mechanics index decoupled from the pilot graphics.

## Rank (F8): who changes BL's rank, and by how much (`rank_writes.lua`)

Write tap on BL's stored rank `0C297A3C` (low 32 bits of the 64-bit bus word `0C297A38`), keyed by writer PC,
return address (PR) and delta, over ~12,000 frames of scripted play:

| writer (helper) | caller | caller's arcade original → PS2 | delta (stored; − = harder) |
|---|---|---|---|
| `0C071CA0` | `0C07E5C0` | `0C06D4C0` → PS2 type-2 pickup `0x0012F400` (**bomb fragment**) | −0x40000 (×57) |
| `0C071CA0` | `0C07D010` (next-medal) | `0C06BA60` → ? | −0x20000 … −0x80000 |
| `0C071CA0` | `0C07E160` (streaks) | `0C06D0B0` → ? | −0x80000 |
| `0C071CD4/CD6` | `0C07E440` | `0C06D370` → ? | ±0x80000 … +0x180000 |
| `0C071CA0` | `0C0BC020`, `0C0BBF10` | (literal-only vs arcade) | −0x1000 |
| `0C06D302`, `0C06D6FC` | player start, title | — | set |

PS2 fragment handler: Arcade path `harder(0x2000)` at `0x0012F4A4`; Arrange adds `harder(0x40000)` at
`0x0012F504`. BL uses Arrange's 0x40000. PS2 rank helpers: `0x00129DC0` easier (+, capped),
`0x00129DF0` harder (−); both do nothing while `$gp-0x6DB0` (`0x00338F40`) is non-zero (stage start).

### Rank attribution to item kinds (`rank_attribution.lua`)

Per frame, a rank write is attributed to the pickup kind whose BL streak counter (`0C22E2AC + kind`) rose:
`0C07E5C0` ← **fragment** (−0x40000), `0C07D010` ← **medal** (0, −0x20000 … −0x80000 = level × 0x20000),
`0C07E440` ← **score item / rose** (mostly +0x80000, also +0xC0000; easier). These are Arrange's rules on PS2:
medal `0x0012F7B0` Arrange branch `harder(level << 17)`; rose `0x0012F680` Arrange branch
`easier(table[level] × 1024)` with table `0x0020BFD0` = 0x100/0x200/0x300/0x400 (Arcade uses the same table
unscaled as *harder*). Some BL rose writes (±0x180000, negatives) are unexplained (merged roses or the
easy-end cap?) and are left open.

## Enemy/stage delta: first look (2026-11-20)

* Of Phase 11's 161 "literal-only" BL routines, **109 differ only by record layout** (player stride
  0x280→0x2A0 and shifted fields, item record 0x54→0x60). Of the other 52, ~30 share one change
  `0x40 → 0x44` (a field of BL's enemy object moved by 4) and others are buffer sizes (`0x340→0x680`,
  `0x5400→0x6000`). Real rule changes found there: the **score cap 99,999,999 → 999,999,999**
  (`0x5F5E0FF→0x3B9AC9FF`, BL `0C065890` / arcade `0C053E90`; the PS2 ELF contains neither constant, so the
  port applies no such cap and already behaves like BL in practice) and a few small counts (`3→2`, `0xA6→0xA5`) still
  to be identified. Literal patching is therefore *not* a route to BL's enemy behaviour.
* `enemy_records.lua` samples live BL enemy parts in stage 1 and dumps their `+0x10` records (sprite-animation
  lists: pointer, duration, flags). 10 of 11 have a structural match in the PS2 ELF (BL pointers ↔ PS2 pointers,
  scalars equal), but the lists repeat, so matches are not unique. They show the same data types, not BL behaviour.

**Implication:** BL's enemy changes live in ~290 *structurally changed* routines (Phase 11). They need per-routine
porting (MAME to observe, BL code to read, PS2 counterpart to patch or replace), stage by stage, starting with
stage 1. Measuring which enemy types and scripts stage 1 uses in BL vs the PS2 Arcade mode is the next step.
