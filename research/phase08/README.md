# Ibara Complete — Phase 8: Pickup dispatch, medal scoring, and rank crosswalk

**Status:** Read-only original Japanese PS2 retail ELF investigation, no changes to ISO, no emulator/hardware tests required.

**Baseline:** `SLPM_663.01`, SHA-256 `263d3079dee66af82815219351553075340a4d9f42aceaa7bb8ef2bfb812ffac`, extracted from user-owned original `Ibara (Japan).iso`.

This report concerns PlayStation 2 EE MIPS addresses, **not** the arcade CV1000 SH-3 executable. The core result is an independently verified chain from player/item intersection to a type-specific dispatch table and data-driven point awards.

## 1. Confirmed end-to-end pickup path

| Address | Static evidence | Interpretation |
|---|---|---|
| `0x0012A61C` | Direct `jal 0x0012FD00` in a player/item bounding-box intersection routine | Item-pickup processing entry |
| `0x0012FD00` | Item index in `a1`, accesses item record `+4`, stores field as item type | Type-specific item handler dispatcher |
| `0x0012FDA4` | `jalr $v0`; code loads eight function pointers from `0x0020BF60` into stack slots before indexing | Indirect dispatch across **eight** item types |
| `0x0020BF60` | Exactly eight addresses in executable data | Handler table; see CSV |
| `0x0012EBF0` | Common award path, called by all relevant handlers | Reads item `+4` as type, `+8` as reward-level index; selects type table via `0x0020BE80` |
| `0x0012EC84–0x0012EC94` | Loads field `+4` from 16-byte reward metadata, adds it to player score and stores | Data-driven score increase |

The award routine uses item records at `0x00453A40 + slot * 0x58` and player score words at **`0x0044C600 + side * 0x290`**. The eight per-type scoring metadata pointers reside at `0x0020BE80`, two words per type.

The original game's collision/dispatch order is evidenced by its MIPS code, but when exactly this routine executes relative to bomb/shot effects is not yet established by a runtime trace.

## 2. Verified eight item handlers and score metadata

| Type | Handler | Reward table start | Directly verified point values | Identification |
|---:|---|---|---|---|
| 0 | `0x0012FB00` | `0x00208790` | 100 | Small P? (tentative from original arcade mapping) |
| 1 | `0x0012EDC0` | `0x00209700` | 10,000 (first eight entries) | Option? (tentative) |
| 2 | `0x0012F400` | `0x00208920` | 500 | Bomb fragment? (tentative) |
| **3** | **`0x0012F7B0`** | **`0x0020B100`** | **100, 200, ... 10,000** (19 entries) | **Medal** (strongly identified by score ladder and 19-level handling) |
| 4 | `0x0012FA10` | `0x00208AB0` | 1,000 | Large P? (tentative) |
| 5 | `0x0012F570` | `0x00208C40` | 5,000 | Full bomb? (tentative) |
| 6 | `0x0012F930` | `0x00208600` | 10,000 | 1UP? (tentative) |
| **7** | **`0x0012F680`** | **`0x0020BD00`** | **100, 200, 400, 800** (two sets) | **Score item**, consistent with arcade labels; exact PS2 item artwork and creation events still not fully traced |

Tentative labels are informed by the arcade Ibara mapping published in the public `ibara360` project's `host/xsdk/ibara360/source/gadgets.c`; **only the numeric type IDs, handlers and point values are verified directly on PS2**.

### Medal score values

At `0x0020B100`, each medal has a 16-byte descriptor; the points are the word at `+4`. All **19** levels were verified against the retail ELF: levels 1–10 award 100–1,000 by steps of 100; levels 11–19 award 2,000–10,000 by steps of 1,000. The `medals.csv` file includes every level.

## 3. Important mode difference: medals and rank

Medal handler **`0x0012F7B0`**, indexed at `0x0020BF6C`, reads a medal level, calls the generic point-award routine, and performs a **rank-decrease operation** in both modes. Since the rank variable is inverted (smaller stored rank means *harder*), both paths can raise difficulty but by vastly different amounts.

- **Arcade (mode flag zero):** `0x0012F81C` calls stored-rank decrease `0x00129DF0`, loading a delta from the **19-entry table at `0x0020BF80`**. The table is `[256] x 9`, `[1024] x 9`, `[4096] x 1`.
- **Arrange (nonzero):** `0x0012F834` also calls stored-rank decrease, but passes `medal_index << 17` instead of consulting that table. For medal index 0, this path passes zero; at index 18, 2,359,296. These are arguments to the rank function, not guaranteed final changes: its guard/clamping behavior still applies.

Thus there is **no one universal medal-to-rank formula** shared by retail Arcade and Arrange. Any Kuro implementation must adopt Kuro's actual rules, not silently combine the two.

## 4. Type 7 (score item) in the two modes

- Arcade handler `0x0012F6E0` calls rank **decrease** (`0x00129DF0`) with a value indexed into the four-word table `0x0020BFD0` containing **256, 512, 768, 1,024**.
- Arrange handler `0x0012F708` calls rank **increase** (`0x00129DC0`) with the selected table value shifted left by **10** (multiplied by 1,024). This makes the stored value larger, which **lowers difficulty**, subject to the existing clamp/guard logic.

The award metadata contains eight reward entries for this type, while the rank table has only four entries. **This is not a proof all eight entries can be selected for every rank path:** the live index's valid range and potential masks need a further dataflow trace.

## 5. Correction to earlier score research

**Read `PHASE6-7_ERRATA.md` before any debugger or patch work.** Phases 6–7 accidentally placed all absolute PS2 player record and score addresses `0x10000` too high. They should be `0x0044C380` (P1 record), `0x0044C600` (P1 score), etc. The `lui` and signed `addiu` instruction words prove this unambiguously.

Also, `0x00134E90` is a **max(a,b)** helper. Its caller at `0x0012AC18` uses `max(object[0x40],object[0x44])` as a dynamic award amount, then adds it to the score. That path is distinct from the common item-score lookup and is not identified as a medal multiplier.

## 6. What is still unknown

1. **Bullet cancellation:** Static evidence here does not fully identify bomb/Hadou cancellation entry points, bullet deletion rules, or whether direct cancellation scores points or spawns pickups. We will not claim to have solved it without an explicit function/branch chain.
2. **Exact identification of non-medal item types:** Confirm the labels by linking their specific spawn and pickup caller paths to their artwork/flags; current labels other than medals are tentative.
3. **Kuro-specific behavior:** The retail PS2 tables describe Original/Arrange, not Kuro. Authentic Black Label needs separate Kuro rank, XTC, scoring and conversion logic. The project `ibara360` is an implementation reference, not proof the EE engine matches Kuro.
4. **Perf and real-hardware behavior:** Not tested in this phase. No numerical timings or gameplay assertions are implied.

## 7. Reproduce with the original disc (Windows / macOS / Linux)

The audit has no dependencies beyond Python 3.10+. It only reads a bounded 2.33 MB ELF from the input file, so it can verify an ISO without copying or modifying the 3.9 GB image.

```bash
python audit_pickups.py "SLPM_663.01" --json report.json --csv pickups.csv --medal-csv medals.csv
python test_audit_pickups.py "SLPM_663.01"
```

Or point `audit_pickups.py` at the **exact unmodified Japanese ISO**. The auditor checks the SHA-256 and verified MIPS instructions and fails closed for other revisions. Do not use it on already-modified builds.

The included audit outputs were obtained from **both** the original extracted ELF and the retail ISO. Ten automated tests passed, including modified-data rejection tests. No copyrighted game code, artwork, executable or ROM is distributed in this package.

## Useful upstream research

- `ibara360`: https://github.com/PaulAtreides67/ibara360
- Arcade memory and pickups: https://github.com/PaulAtreides67/ibara360/blob/main/host/xsdk/ibara360/source/gadgets.c
- Reconstructed Arrange patch records (not directly portable EE instructions): https://github.com/PaulAtreides67/ibara360/blob/main/gen/ibaraarr/arrange_patch.c
