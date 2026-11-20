# Phase 11 — Measured Black Label delta (arcade Ibara → Ibara Kuro BL)

**Question:** what does Black Label change, in code, compared with arcade Ibara? The answer sizes the PS2
port and tells us which PS2 routines must change.

**Method:** the public `ibara360` project ships static SH-3 → C recompilations of both arcade programs
(`gen/ibara_drc`, `gen/ibarablk_drc`). Every instruction is annotated with its SH-3 address and mnemonic.
`sh3_drc_diff.py` reads those annotations from a **local** checkout (nothing from ibara360 is bundled; it
has no license file) and matches functions between the two programs:

1. unique exact-shape hash (address literals masked),
2. unique mnemonic-sequence hash (literal values changed),
3. call-graph propagation from matched pairs,
4. order-preserving gap fill between anchors (mnemonic similarity ≥ 0.55),
5. global pass over the remainder (similarity ≥ 0.60, size ratio 0.5–2).

Committed outputs hold only addresses, counts, mnemonics and changed literal values — no generated C.

```bash
git clone --depth 1 https://github.com/PaulAtreides67/ibara360 /tmp/ibara360   # outside this repo
python3 research/phase11/sh3_drc_diff.py /tmp/ibara360 --out research/phase11/out
python3 research/phase11/sh3_drc_diff.py /tmp/ibara360 --b ibaraarr_drc --out research/phase11/out
python3 research/phase11/tag_subsystems.py /tmp/ibara360 research/phase11/out
python3 research/phase11/validate_anchors.py /tmp/ibara360 research/phase11/out
```

## Results (static, ibara360 commit cloned 2026-11-20)

| | arcade Ibara (U4 `d5fb6657`) | Kuro BL (U4 `ee1f1f77`) |
|---|---|---|
| functions | 1,336 | 1,370 |
| SH-3 instructions | 143,003 | 148,385 |

| Match status | count |
|---|---|
| identical (address literals aside) | 745 |
| same shape, literal values changed | 161 |
| changed body | 326 |
| arcade-only (removed/rewritten) | 104 |
| BL-only (new) | 138 (18,886 insns) |

**Estimated delta ≈ 27,800 SH-3 instructions** (Σ changed × (1 − similarity) + new). By the work-RAM
structure each routine references (`tag_subsystems.py`, primary tag):

| Subsystem | functions | ~delta insns |
|---|---|---|
| enemy parts (behaviour, patterns, bosses) | 288 | 16,900 |
| player record (ship select, weapon stock, XTC, bombs) | 91 | 6,900 |
| untagged (mostly small helpers) | 166 | 1,900 |
| camera / scroll | 20 | 780 |
| enemy bullets | 17 | 400 |
| rank | 5 | 350 |
| attract / title | 10 | 250 |
| shots, layers, medal, streaks, stage, bgm | ~25 | ~230 |

**Validation:** 14 of 15 scorable ibara↔BL pairs documented in ibara360's comments (found there by live
tracing, independently of this matcher) agree. The disagreement (`0C05DE00`, continue/score reset) was a
low-similarity match (0.57); ibara360's note may cite code that BL moved into another routine. Treat
matches with similarity < 0.65 as **low confidence** (flagged in `bl_delta_tagged.csv`).

Sanity check: arcade Ibara vs ibara360's Arrange build is 1,148 identical + 186 literal-only, 1 changed, 117
added — consistent with Arrange being implemented as hooks, so the differ is not inventing changes.

## What this means for the PS2 port

* BL is **not** a parameter tweak: ~19% of the program changes, dominated by enemy behaviour. A
  faithful BL needs BL's enemy/boss routines, not the PS2's Arcade ones with new numbers.
* Player-side systems are well specified (ibara360 header notes, `docs/BLACK_LABEL_FEATURES.md`): the
  7-weapon stock and current weapon, straight/spread ship select, XTC graze counter, shot top level 5,
  player record stride 0x2A0.
* PS2 Arrange already has stored sub-weapons offered in BL's HUD order and rank-lowering cancels, so
  for player systems Arrange is the closest PS2 base. Enemy behaviour must come from BL itself.

See `docs/BLACK_LABEL_PORT_PLAN.md` for the architecture decision this feeds.

## Files

| File | Content |
|---|---|
| `out/ibara_vs_ibarablk_functions.csv` | every function: arcade addr, BL addr, status, method, similarity, sizes |
| `out/ibara_vs_ibarablk_details.json` | per changed function: mnemonic diff hunks, changed literal values |
| `out/ibara_vs_ibarablk_ram_map.csv` | arcade → BL work-RAM address map from aligned literals (295 entries) |
| `out/bl_delta_tagged.{csv,json}` | BL changed/new functions tagged by referenced structure |
| `out/anchor_validation.json` | matcher vs ibara360's documented pairs |
| `out/ibara_vs_ibaraarr_*` | control comparison against ibara360's Arrange build |

Confidence: **static only**. Function matching is heuristic; addresses are SH-3 arcade addresses
(`0C......`), never PS2 EE addresses.
