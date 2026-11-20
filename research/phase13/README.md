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
