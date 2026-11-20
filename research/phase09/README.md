# Ibara Complete — Phase 9: Bullet conversion and the Arrange rose multiplier

**Status:** Static analysis completed against the user's *original*, unmodified Japanese Ibara (PS2) `SLPM_663.01`. **This is not a playable Black Label port** and has not been tested in PCSX2 or on a console. No original executable, ISO, sprites, recompiled arcade code or copyrighted assets are included in the research package. Source game files are never changed.

**Exact original ELF SHA-256:** `263d3079dee66af82815219351553075340a4d9f42aceaa7bb8ef2bfb812ffac`  
**PS2 architecture:** Emotion Engine / MIPS, distinct from the arcade CV1000 SH-3 program.  
**Corrections from prior phases:** Use P1 record at `0x0044C380` and P1 score at `0x0044C600`, *not* the obsolete Phase 7 addresses that were 0x10000 too high. See the Phase 8 errata.

## 1. Confirmed native PS2 event path

| Address | Evidence from exact retail ELF | Confidence |
|---|---|---|
| `0x0012E62C` | Per-frame update performs `JAL 0x0012AC60` | Direct verified call |
| `0x0012AC60` | Collision pass with a 0x50-stride player-projectile pool and a 0x54-stride opposing projectile/bullet pool | Explicit code/dataflow; precise object-name labels inferred |
| `0x0012AE40–0x0012AF40` | Collision response branches by object flag, mode, projectile `+0x04` type and `+0x08` subtype | Verified branch path |
| `0x0012AE8C`, `0x0012AEF4`, `0x0012AF0C`, `0x0012AF24`, `0x0012AF3C` | Each calls `0x00121FC0`, passing selector `1`, `0`, or `2` | Five direct verified calls and MIPS argument-delay slots |
| `0x00121FC0` | Helper branches on selector values 1 and 2, with a further object/lifecycle dispatch | Verified code; full lifetime semantics still unresolved |
| `0x001220FC` | Calls `0x001306D0` with item type `7` | Verified item-creation call |
| `0x001220A0` | Calls `0x001306D0` with item type `3` | Verified item-creation call |
| `0x001306D0` | Finds a free item entry at `0x00453A40 + i * 0x58`, sets item coordinates, calls initializer `0x001308A0` | Verified store/index code |
| `0x0012A61C` | Separate pickup collision routine calls `0x0012FD00` | Verified direct call; exact call timing vs cancellation not traced |
| `0x0012FD00` | Dispatches item pickup by type using the eight-entry handler table (Phase 8) | Verified in Phase 8 |
| `0x0012F680` | Type-7 handler, separates Arcade and Arrange scoring/rank | Verified in Phases 8–9 |

The pools in the cancel collision routine are rooted at `0x0044EA40` (player-side projectile records, stride `0x50`) and `0x004682EC` (candidate opposing bullets, stride `0x54`); the item records begin at `0x00453A40` with stride `0x58`.

**Semantic caution:** The code proves an item conversion pathway after a particular collision and code flags. It does not prove every bomb/Hadou effect in every game situation passes through that path, or that selector 0 necessarily leaves a projectile untouched. Selector 0 calls the removal/conversion helper but does not generate an item *inside that helper*. Its separate lifecycle-dispatch behavior needs a runtime test or more disassembly.

## 2. The mode-dependent conversion selector

The branch decision at `0x0012AE50–0x0012AF40` occurs only once the relevant projectile/object and hitbox checks pass. In the table below, *no item* means no item-spawn call in this path. It does **not** mean the bullet survives.

| Mode | Player projectile type (`+0x04`) | Subtype (`+0x08`) | Helper selector | Item from helper |
|---|---|---|---|---|
| Arcade | Any in the verified branch | Any | `1` | Type `7` rose/score item |
| Arrange | `1` or `2` | `0` | No helper call from this branch | None in this path |
| Arrange | `1` or `2` | `1` | `2` | Type `3` medal |
| Arrange | `1` or `2` | Anything else | `0` | None in this path |
| Arrange | `0`, `9`, or `10` | Any | `0` | None in this path |
| Arrange | All other types | Any | `1` | Type `7` rose/score item |

The item-type labels **7 = rose** and **3 = medal** are strongly corroborated by verified PS2 reward values and independent Arcade scoring descriptions (100, 200, 400, 800 roses and 100–10,000 medals). The projectile-type *weapon names* (which represent the bomb, Hadou missile, explosion, trail, etc.) have **not** been identified, so the model correctly retains their numeric IDs. An exhaustive CSV of 48 representative type/subtype cases is in `selector_cases.csv`.

## 3. Finding: PS2 Arrange's rank-based rose multiplier

This is a particularly useful intact piece of the retail PS2 engine. It establishes a version of the Baradise-style reward system without reconstructing a full emulator.

**On creation** at `0x00130810–0x00130850`:

- When the current mode is Arrange and the new item is type `7`, the item stores a multiplier-like factor at item offset `+0x54`.
- It is derived from the current *inverted stored rank* at global `0x00338EB4`: `factor = (0x01000000 - stored_rank) >> 16` (for valid 24-bit stored rank).
- The factor is floored to `1`. At `factor >= 256`, the code explicitly replaces it with `300`; i.e. at rank `0x000000`, the result is 300, not 256. This is **not** a continuous 1–300 scale.
- The code also passes this factor to a visual-effect call; it is not the score itself.

**On collection** at `0x0012F730–0x0012F784`:

The original binary reads `item[+0x08]` and `item[+0x54]`, calculates `10*item[+8]+30`, then executes a three-register Emotion Engine MULT (`0x00433818`: `mult $a3,$v0,$v1`, R5900 encoding) and adds `$a3` to the player score.

Therefore the item-collection formula is:

```
Arrange rose points = (10 * item_level + 30) * factor_at_creation
```

This is *not* an automatic score bonus on every bullet canceled. The player must collect the item, and the score depends on the level field and the rank factor captured at spawn. Item-merging/progression may change `item_level` afterward; that complete event sequence needs a separate audit. The quoted `10 * level + 30` is from native instructions and does not substitute any assumed arcade Kuro formulas.

### Calculated examples (not recorded gameplay)

| Inverted stored rank at spawn | Spawn factor | Collected level 0 points | Collected level 3 points |
|---|---:|---:|---:|
| `0xFFFFFF` (minimum difficulty) | 1 | 30 | 60 |
| `0xF00000` | 16 | 480 | 960 |
| `0x800000` | 128 | 3,840 | 7,680 |
| `0x010000` | 255 | 7,650 | 15,300 |
| `0x000001` | 255 | 7,650 | 15,300 |
| `0x000000` (maximum difficulty) | **300** | **9,000** | **18,000** |

**On type-7 pickup**, the rank system is also mode-dependent (see Phase 8): Arcade lowers the inverted stored rank (harder) by table-driven amounts, while Arrange raises the stored rank (easier) using an amount multiplied by 1024. The rank change and score award are **different operations**.

## 4. Why Kuro cannot simply enable Arrange's code

The public `ibara360` project's Kuro implementation and its independently documented code show that:

- The Kuro `0x0C06EF50` SH-3 graze routine checks a bullet flag and player input state, including the held-A duration at player offset `+0x270` and option-pod status at `+0x289`.
- The public author's `gadgets.c` commentary maps the Kuro Xtreme Terror Counter at `+0x280` and timer at `+0x284`; it documents the 9,999 visible maximum, and its interaction with graze scoring.
- Kuro uses an XTC/Baradise interaction, including how rose conversion and rank are scored, that **is not present in the native PS2 Arrange rose formula we found**.
- Independent gameplay research also describes Kuro's auto-pickups and different option/weapon behavior.

This is enough to define separate engineering workstreams: retain the PS2 projectile collision and type-7 item systems where appropriate, *implement Kuro's XTC state and scoring separately*, and only combine after testing against the actual arcade reference. It does **not** establish numerical parity with Kuro.

Public sources:
- https://github.com/PaulAtreides67/ibara360/blob/main/gen/ibarablk_drc/blk_recomp_06.c (SH-3 Kuro `0x0C06EF50`)
- https://github.com/PaulAtreides67/ibara360/blob/main/host/xsdk/ibara360/source/gadgets.c (Kuro XTC mapping and behavior)
- https://shmups.wiki/library/Ibara (Arcade roses and PS2/Arrange descriptions)
- https://www.hardcoregaming101.net/ibara/ (Arrange Baradise and Kuro differences)

## 5. Next independent tasks

1. **Identify the five numeric projectile categories** in the PS2 conversion branch by tracing the code that creates player-projectile records (`0x0044EA40`, stride `0x50`) and sets their `+4` and `+8` fields. Only then can we label exactly which are bomb/Hadou/trail variants.
2. **Analyze item merging and rose-level progression** to determine when the `+8` field increments and whether all reward multipliers remain based on spawn rank (`+0x54`).
3. **Trace secondary score/cancellation routes** for boss destruction and the player death animation. The call path above is one verified branch, not necessarily all ways roses are generated.
4. **Implement Kuro XTC as a separate model**, initially with simple event inputs, and validate each numerical rule against the SH-3 recompilation and arcade recordings before writing any EE patches.
5. **Only then plan MIPS code injection** using free space and confirmed hook sites, retaining native 240p and the retail Arcade/Arrange branches.

## 6. Run the read-only audit

Requires Python 3.10+, no nonstandard dependencies. The tool reads at most the embedded 2.33 MB ELF from the ISO and does not copy the entire disc.

```sh
python audit_cancellation.py "SLPM_663.01" --json report.json --csv selector_cases.csv
python test_audit_cancellation.py "SLPM_663.01"
```

Alternatively specify the original `Ibara (Japan).iso` for both commands. The tool **refuses modified or unknown revisions** based on an exact SHA-256 of the executable and independently verifies 75 MIPS instruction words plus 13 JAL edges. The tests mutate copies held in memory to ensure altered instructions are rejected. The audit neither boots the game nor measures performance; all results are explicitly static.
