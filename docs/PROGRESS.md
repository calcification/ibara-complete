# Progress report — 24 November 2026

Where Ibara Complete stands: the retail PS2 Ibara (SLPM-66301) plus **KURO**, the Black Label rules switched on
from Mode Select. Arrange stays as on the original disc, with one addition: a PRACTICE row. Delivered as
`patcher/` (a 9.8 KB patch; no game data in the repository). Black Label art comes from the user's own `ibarablk`
ROM (`--bl-rom`).

## How far along

The percentages below are an estimate from the feature checklist (`docs/BLACK_LABEL_FEATURES.md`) and the test
matrix. They are not a measurement.

| Area | Done | Estimate |
|---|---|---|
| Disc, menus, delivery | KURO row in Mode Select, switched on instantly without a reload; patcher (Windows drag-and-drop / Python); `--bl-rom` art injection; byte-identical rebuild check; repository safety check | ~95 % |
| Video | Yoko interlaced without filtering, Tate 240p progressive, switched live and kept on the memory card | done; passed on an original PS2 (K41) |
| Player rules (F1–F7, F10) | XTC graze counter + HUD + bomb wipe; weapon stock + change button; shot levels to 6, no secret; held fire every 2 frames; 32-shot cap; pod aiming, pod fire rules, no rank per pod shot; BL hit sparks; bombs (no rank, type D by ship); straight/spread A–D; bullet cancel after bosses and mid-bosses | ~85 % |
| Rank (F8) | stored-rank format, fragment / medal / rose / item rules at BL's amounts, no time creep or shot cost (K43), bombs as BL, enemy fire timer from rank, RANK bar | ~90 % (Hadou drops open) |
| Enemies and stages (G5–G7) | BL enemy HP, part HP all stages, fire timer, bullet cancel; stages 1–3 and 5 compared enemy by enemy and matching; stage scripts diffed for all six stages, stage 5's extra waves ported (K44) | ~55 % — open: stage 4 mid-boss and boss timelines, the boss BL adds after stage 6 (with game flow), player-side damage |
| Presentation (F11, A1) | BL RANK bar (exact colours); BL select screen (ship → type → confirm, 60-s timer, BL layout and art, BL ship-select theme from the user's sound ROMs); graze sphere and XTC popup | ~60 % (select animation / fly-in / runway background; title logo; XTC rank glow and graze sound) |
| Arcade slowdown (Codex, phase 22) | Arcade CONFIG → SLOWDOWN (default Off); L2 + R2 toggles manual half speed in Arcade; cleared when leaving to the menu; Noir and Arrange untouched | manual mode ~90 % (menu-reset retest on hardware pending); automatic arcade-like slowdown ~15 % (research only: no predictor yet reaches the 80 % event target on held-out captures) |
| Game flow (G1–G3) | KURO enters through Arcade's menu | ~30 % (single 6-stage loop rules, opening record, side select) |

**Overall: roughly 70 %** toward a Black Label mode that plays like the arcade. Nearly everything the player touches
directly is done and checked against MAME. Most of what's left is enemy and stage behaviour, plus presentation.

Tests: 70 entries in `TEST_MATRIX.csv`, 44 PASS (K02–K42 pass; the S-rows are the slowdown research and console checklist, mostly READY / PENDING). Every KURO row from K02 to K30 passes; K01 (the early attract-demo
check) is superseded by K03. The rest are older optional or hardware rows. Unit tests: 64 pass.

## Done since the last report

* **KURO select screen** (K29), stage one, art from the user's ROM. The freezes on the way came from a stack-alignment
  bug in all hook code (8-byte o32 frames; a thread switch corrupted `gp`). Hooks are now built as n32 with
  16-byte frames, and a test checks every frame.
* **Hit sparks as BL** (K30). This was the "MG pod margin" item. MG pod shots per 1,000 frames: 317 → 209 (BL 208).
* Carry-over notes for the next project (`docs/NEXT_MUSHIHIMESAMA.md`).

## Next, in order

1. Finish the XTC rank glow and graze sound. The graze sphere (K31), number popup (K32), and deployed-pod requirement are implemented.
2. Pod shot counts still apart from BL: 5-way, homing, napalm (targeting / fire rules).
3. Hadou drops (BL: medals and type-11 items, no roses), with the item and enemy comparison.
4. Stage 4 mid-boss and boss timelines (no-shot runs); then the boss BL adds after stage 6, together with game flow G1–G3.
5. Select screen stage two (animation, fly-in, girder background, player 2); BL title logo.
6. Game flow G1–G3.

## Since 23 November

* **Black Label ship-select theme** (K42). Decoded from the user's sound ROMs (`u23`/`u24`) and added to the
  disc's resource archive without growing it. It loops while the selector is up and stops at takeoff
  (research/phase23). It still needs a listen on hardware.
* **Rank rules** (K43). Noir dropped four Arcade rank rules that Black Label doesn't have: a harder step every
  frame, a cost per shot, a cost per item pickup, and half-size rose amounts. Rank now moves only on BL's
  events, with BL's amounts (research/phase24).
* **Stage comparisons** (K44). Stages 3–6 were compared with Black Label, and all six stage scripts were diffed.
  Stage 3 matches. Stage 5 was missing six enemy waves, and Noir now has them. Stage 4's mid-boss and boss
  timelines still differ. After stage 6, BL goes on to another boss (research/phase25).

## Known gaps

* The K40 build passed the full checklist on an original PS2 (K41, 23 Nov 2026).
* While the select screen is up, the stage isn't drawn (black background). The HUD's "♪Show Time" track
  line still shows (BL has no Show Time).
