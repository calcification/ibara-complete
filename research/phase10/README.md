# Ibara Complete — Phase 10: Rose merging, accumulated multipliers, and projectile producer

**Status:** Read-only static analysis of Japanese retail PS2 Ibara `SLPM_663.01`. Every offset listed as *verified* below was inspected in the original, unchanged ELF and checked by the included auditor. The same ELF was extracted from the user's retail ISO. **No emulator, console, or gameplay execution was performed.**

This phase follows the Phase 9 cancellation/scoring audit, which traced bullet conversion to item type 7 and found the native Arrange rose award formula. Phase 10 answers what happens to that formula when two roses are combined.

## 1. The item update table really sends roses to a merging routine

The **eight-entry** item *update* dispatch table at EE address `0x0020BF00` contains:

| Index (item type) | Handler EE address |
|---:|---:|
| 0 | `0x001323D0` |
| 1 | `0x001323D0` |
| 2 | `0x001323D0` |
| 3 (medal) | `0x001322F0` |
| 4 | `0x001323D0` |
| 5 | `0x001323D0` |
| 6 | `0x001323D0` |
| **7 (rose/score item)** | **`0x00132BC0`** |

This is a different function-pointer table from Phase 8's pickup *collection* handlers. The type-7 updater performs ordinary item motion/state work, then at:

- `0x00132DC0` — reads `item+0x08`, the item level.
- `0x00132DC4` — `slti ... , 3`: checks whether the *entering* level is **0, 1, or 2**.
- `0x00132DC8` — conditional branch to `0x00132E60`.
- `0x00132E60` — `jal 0x0012EA10`, a generic overlapping-item merge helper; its delay slot passes the item pointer in `$a0`.

Thus type-7 roses participate in this merge path when their current level is below 3. That does **not** mean no other merging or item-leveling paths exist; this is the particular verified route.

## 2. Merge helper: exact decision and commit

The shared helper begins at `0x0012EA10`, traversing an array beginning at **`0x00453A40`**, with **256 items at a stride of 0x58 bytes** (`0x0012EB94` bound, `0x0012EB9C` increment). Its decision checks include:

| EE address | Check or action |
|---|---|
| `0x0012EA70` | Skip the current item itself |
| `0x0012EA78–0x0012EA7C` | Skip unused/inactive target slots |
| `0x0012EA84–0x0012EA8C` | Read and compare item type at `+0x04` |
| `0x0012EA94–0x0012EA9C` | Read and compare item level at `+0x08` |
| `0x0012EAA4–0x0012EB08` | Read shape/collision information and test both axes for overlap |
| `0x0012EB10–0x0012EB1C` | Increment surviving item's `+0x08` level by **one** |
| `0x0012EB64` | Update surviving item's `+0x30` animation/state field |
| `0x0012EB68` | Zero absorbed item's `+0x00`, removing it |
| `0x0012EB6C–0x0012EB7C` | **Add absorbed `+0x54` factor into surviving `+0x54` factor** |

The store at `0x0012EB7C` is the **MIPS branch delay slot** of the unconditional branch at `0x0012EB78`. It executes *before* the helper jumps to its return path `0x0012EBD0`. This implies **at most one successful merge per helper invocation**, not an unbounded chain inside a single call. A survivor could still merge again on a later item update while its level is below 3; that is an inference about future calls, not a gameplay measurement.

### Key memory layout

- `item+0x00`: in-use/active flag (zeroed for absorbed item)
- `item+0x04`: type
- `item+0x08`: level
- `item+0x1C`: pointer to item shape/collision data
- `item+0x28`, `+0x2C`: position
- `item+0x30`: animation/state data
- **`item+0x54`: Arrange rose score factor, accumulated across merges**

## 3. Critical Phase 9 refinement: 300× is a *spawn* ceiling, not a merge ceiling

Phase 9 established that in Arrange the game initializes `item+0x54` at `0x0013081C–0x00130850`, using an inverted rank-derived factor. The factor when the rose is first created is clamped to `1..300`.

However, the Phase 10 merge helper performs this operation:

```
survivor.factor = (survivor.factor + absorbed.factor) mod 2^32
```

It **does not apply the 300 cap afterward**. Therefore, the source of the factor matters:

- Individual spawned roses have factors in the documented 1–300 range.
- Merged roses can hold a combined factor exceeding 300.
- The collection code remains `(10 * item_level + 30) * accumulated_factor`; the result is not limited to 300× by the merge helper.

For clarity, the script's `rose_points()` reports the **raw, 32-bit EE arithmetic award** before any other possible display/score saturation, and it accepts accumulated factors larger than 300. This corrects Phase 9's *Python model* input validation: it incorrectly rejected merged factors greater than 300, though the native formula does not.

**Illustrative arithmetic only** (assumes two roses meet all merge conditions; not measured game outcomes):

| Before merge | Separate raw collection | Merged level/factor | Merged raw collection |
|---|---:|---|---:|
| Two level-0 roses, factors 100 and 50 | `30×100 + 30×50 = 4,500` | Level 1 / 150 | **6,000** |
| Two level-0 roses, factors 300 and 300 | `18,000` | Level 1 / 600 | **24,000** |
| Two level-2 roses, factors 100 and 50 | `7,500` | Level 3 / 150 | **9,000** |

A level-3 survivor does **not** enter this type-7 merge path again because of the updater's `level <3` gate. Distinct item constructors can initialize type-7 items directly at higher levels, so this is not a universal item-level maximum.

## 4. An additional result: multiple type-7 item constructors

There are at least two routes that set an initial item level using the game's random helper at `0x00110FE0`:

1. **Alternate type-7 constructor** beginning `0x001304E0`: assigns type `7`, calls `0x00110FE0` with parameter `4` (`0x001305B8`), and adds 4 to the result before writing `item+0x08` (`0x001305C0–0x001305C8`). This can spawn roses *above* the low-level merge range, depending on the random-helper result.
2. **Mode-dependent item initializer** at `0x001308A0`: on the Arcade branch (`0x00130900–0x00130904`), it calls `0x00110FE0` with argument `7` (`0x00130AA8–0x00130AAC`) and stores the result at `item+0x08` (`0x00130AB4`). The Arrange branch follows a different level-selection route.

The precise random-number distribution is not measured here. These paths should not be conflated with the dynamic level increment caused by merging.

## 5. Projectile identification: one verified numeric producer, not yet a weapon name

We also traced the emitter at **`0x0011A580`** through the player projectile-array structure:

- Pool base: `0x0044EA40`, two player-side regions with records of **`0x50` bytes**.
- The allocation scan checks up to **128 slots** (`0x0011A5DC`), advancing by `0x50` (`0x0011A5E4`).
- After a free slot is found, the initialization path writes **zero to projectile type `+0x04`** at **`0x0011A6AC`**.
- The path is reachable when allocation succeeds; the near-branch at `0x0011A5F4` can be reached with success set by the branch/delay-slot sequence at `0x0011A7D4–0x0011A7D8`.

Thus **one live initializer emits projectile ID 0**. We have **not established whether that numeric type is a particular normal shot, bomb, Hadou, or trail**. Nor have we mapped all writers of types `1`, `2`, `9` and `10`. Phase 9's conversion decision table remains numeric until those writers are traced to player input and weapon paths.

## 6. What this means for a PS2-native Black Label mode

- We can preserve the original game engine's existing item pool and overlapping-item merger rather than building a new one for roses.
- We **must not** clamp merged factor back to 300 when modeling native Arrange.
- Kuro's own scoring is not established by the Arrange formula, and Kuro has additional mechanics including XTC. Adapting Arrange is still a **research direction**, not a proven arcade-accurate replacement.
- The next high-value task is to build a **writer/use cross-reference for projectile type `+0x04`**, identify the real weapon/projectile naming, and trace the particular bomb and Hadou branches to Phase 9's selector. That does not require PCSX2, but gameplay tests will eventually be necessary to validate real behavior.

### Public comparator code (not copied into this package)

- [ibara360 public recompilation and CV1000 runtime](https://github.com/PaulAtreides67/ibara360)
- [PS2 Arrange patch manifest in ibara360](https://github.com/PaulAtreides67/ibara360/blob/main/gen/ibaraarr/arrange_patch.c)
- [Kuro SH-3 recompilation code](https://github.com/PaulAtreides67/ibara360/tree/main/gen/ibarablk_drc)

The original retail executable's MIPS offsets are a different address space and CPU architecture than Kuro's arcade SH-3 offsets. Do not transplant offsets.

## 7. Reproduce the checks

Requires Python 3.10+ (standard library only). On Windows use `py -3` instead of `python` if preferred; commands on macOS/Linux are identical.

```bash
python audit_rose_merging.py "SLPM_663.01" --json report.json --csv instruction_anchors.csv
# or directly use a 2048-byte-sector ISO (no extraction required):
python audit_rose_merging.py "Ibara (Japan).iso" --json iso_report.json
# for the test suite, place the original ELF beside the scripts, or set IBARA_ORIGINAL_ELF
python -m unittest -v test_audit_rose_merging.py
```

The auditor checks the **exact original ELF SHA-256** (`263d3079dee66af82815219351553075340a4d9f42aceaa7bb8ef2bfb812ffac`), **82 frozen instruction words**, **4 MIPS JAL target edges**, the eight-entry table, three loop/dispatch branch targets, and the early exit. It does not write to its input. Its unit tests check known-good and deliberately corrupted cases.

**Built and verified for this phase:** script, unit tests, original-ELF and ISO JSON reports, machine-readable original-instruction anchor CSV, and test log. No disc, ELF, game textures, or arcade ROM assets are distributed.
