> **CRITICAL ERRATA (discovered Phase 8):** Some absolute player-record/score addresses below are wrong by +0x10000. Use `docs/ERRATA.md` and the corrected Phase 8+ documents; do not set PCSX2 breakpoints for the superseded addresses. Historical report preserved for provenance.

# Ibara Complete — Phase 7: Retail PS2 Rank, Scoring, and Extend Audit

**Status:** Static reverse-engineering research, no gameplay patch, **no console/emulator testing required**.

**Source:** Original Japanese *Ibara* PS2 executable `SLPM_663.01` from the user-owned unmodified `Ibara (Japan).iso`, fingerprinted with SHA-256:

`263d3079dee66af82815219351553075340a4d9f42aceaa7bb8ef2bfb812ffac`

This report is a map of **actual PS2 EE instructions**. Its address numbers are not addresses from the arcade CV1000 SH-3 program. No code or game binaries are included in the package. Run `audit_rank_scoring.py` against your own ELF or ISO.

## 1. Confirmed physical address model

- ELF entry VA `0x00100008`; executable load VA `0x00100000`, segment file offset `0x80`. Disc image at sector **1919173** (2048 bytes/sector). File offset for an EE address: `(VA - 0x00100000) + 0x80`.
- Global pointer `gp=0x0033FCF0` (read from ELF `.reginfo`).
- Game-mode discriminator: `lw -0x6DAC($gp)` = EE RAM **`0x00338F44`**. The relevant branches take the **zero** branch for Arcade and **nonzero** for Arrange; this usage was confirmed against these local instructions, not asserted as a universal meaning throughout the game.
- Stored rank: `lw/sw -0x6E3C($gp)` = **`0x00338EB4`**; upper bound at `-0x6E44($gp)` = **`0x00338EAC`**.
- PS2 player-record base `0x0045C380`, stride **`0x290`**. P1 score `0x0045C600`; P2 score `0x0045C890`; P1 next-extend threshold `0x0045C604`, P2 `0x0045C894`; player reserve lives/stock byte at `+0x25A`.

## 2. Rank representation (verified)

**Important inversion:** a smaller stored value means a *higher* visual rank. The display path at `0x00129518–0x00129534` computes `0x00FFFFFF - stored_rank` and scales the result right by eight bits.

Arrange initialization at `0x0012CC7C–0x0012CC90` writes `0x00FFFFFF` to the current value and ceiling; Arcade initialization takes values from per-mode tables instead. The rank calculation uses a mode-dependent guard at `-0x6DB0($gp)`.

### Two rank arithmetic routines

| Purpose | PS2 EE function | Exact static behavior |
|---|---|---|
| Stored-rank increase → **easier** | `0x00129DC0` | Reads current `-0x6E3C`, adds `$a0`, clamps against upper bound `-0x6E44`, unless the guard inhibits modification |
| Stored-rank decrease → **harder** | `0x00129DF0` | Reads current, subtracts `$a0` when `< current`. If the decrement would consume/exceed the current value, the Arrange path can clamp to zero; Arcade path can return without writing. Guarded by `-0x6DB0` |

Important nuance: these are not fully identical saturating arithmetic paths in Arcade and Arrange. The mode-specific underflow branch matters. Don't substitute a generic clamp routine when porting behavior.

**Automatically extracted callsite census:** 56 direct `JAL`s to the rank-decrease function and two direct `JAL`s to rank-increase. The attached `rank_calls.csv` has every source address, the call-delay-slot instruction, a basic argument decode, and a cautious contextual label. This is a census of *direct calls*, not indirect call sites or all logic responsible for rank.

## 3. Two identifiable rank-relief paths

### A. Mode-dependent item-record rank handling (`0x0012F680–0x0012F710`)

- Reads an item record's field at **`+0x08`**, indexes a table at **`0x0020BFD0`**.
- First four verified table entries are **256, 512, 768, 1024**. There may be distinct records after these four; do *not* extrapolate the table length.
- **Arcade / zero mode** at `0x0012F6E0`: `JAL 0x00129DF0`; loads the table value directly into `$a0` via the MIPS delay slot. Stored rank decreases, thus difficulty rises.
- **Arrange / nonzero mode** at `0x0012F708`: `JAL 0x00129DC0`; uses `sll $a0, $v0, 10` in its delay slot, multiplying the same table value by **1024**. Stored rank increases, thus difficulty falls.
- Example hypothetical item records with indices 0–3 would have Arrange deltas of 262,144; 524,288; 786,432; 1,048,576, respectively, subject to rank-ceiling clamp.
- **Unresolved:** the semantic identities of the item IDs that index the table; what events call the item record handler; whether the path is specifically rose collection, or another type of item/event. The address-level arithmetic is verified. Describing this as a proven medal-specific path would be premature.

### B. Stock-indexed relief (`0x00138FFC–0x00139028`)

- Reads player byte at `+0x25A`, uses `&7`, indexes a word table at **`0x00213070`**, and calls **`0x00129DC0`** at `0x00139020`.
- Table values: `0x400000`, `0x200000`, `0x100000`, `0x080000`, `0x040000`, `0x020000`, `0x200000`, `0x200000`.
- Adjacent code changes player stock and resets the rank to upper bound in one branch; this is a **candidate** stock/death-related rank-relief mechanism. Exact events need callgraph or runtime confirmation.

## 4. Score handling verified in retail ELF

The engine uses the player-record `+0x280` score word. Examples:

- HUD reads at `0x0012C388` and formats a score through the game number-rendering routine.
- `0x0012A91C–0x0012A930` reads score, adds **10**, and stores score.
- `0x0012ABC8–0x0012ABDC` another **+10** score path.
- `0x0012AC20–0x0012AC2C` adds a dynamic reward calculated immediately beforehand (`JAL 0x00134E90`). The exact award semantics have not been determined.
- `0x0012E4EC–0x0012E504` enforces a score cap **999,999,999** when compared with 1,000,000,000.

These are observed arithmetic operations, *not* a complete map of how medals and bullet cancellations assign points.

### Extend award logic (`0x0013AB30–0x0013AC60`)

- Loads score at `+0x280`, threshold at `+0x284`, and branches on the unsigned comparison.
- For one mode, threshold advances by a global increment at `-0x6E84($gp)`.
- The Arrange path increments threshold by a literal `0x00989680` = **10,000,000**.
- The player's stock byte at `+0x25A` is incremented where it is below the routine's limit.
- Table `0x00213540`, selected by game configuration at `0x0013E294–0x0013E2B0`, contains `0xFFFFFFFF`, 1,000,000, 2,000,000, 3,000,000, 2,000,000, 4,000,000, 6,000,000. This appears to parameterize extend progression; its exact option settings need additional disassembly.

## 5. Arcade Ibara / Kuro: cross-platform comparison (not transplants)

Public research in [`ibara360`](https://github.com/PaulAtreides67/ibara360) documents CV1000 SH-3 memory for original Ibara and Kuro. In [`host/xsdk/ibara360/source/gadgets.c`](https://github.com/PaulAtreides67/ibara360/blob/main/host/xsdk/ibara360/source/gadgets.c), arcade original has rank word `0x0C27DFF8`, score `0x0C283A04`, player base `0x0C283794`; Kuro has rank `0x0C297A3C`, score `0x0C29D468`, player base `0x0C29D1D8`.

The same source describes Kuro's XTC: a counter activated by particular hold/option/bullet graze conditions, with timer and reward behavior. **No PS2 XTC implementation is present or proved** by the audit. These sources can define behavioral test cases or target mechanics; no arcade SH-3 addresses or whole emulator functions should be directly transplanted into the PS2 ELF.

The repository's generated `gen/ibaraarr/arrange_patch.c` describes 368 patch records used to reconstruct PS2 Arrange *on the arcade game*, and offers additional behavioral comparison. The PS2 retail implementation is distinct from that arcade-side reimplementation.

## 6. Remaining unknowns and recommended next static targets

1. **Identify exact item categories** reaching EE `0x0012F680` and `0x0012F7B0` by following direct/indirect caller chains and the item record's `+8` and `+0` fields. This distinguishes roses, medals, bombs, and other pickups.
2. **Trace actual medal score table** and scoring multiplier from score-award writers; `0x0012EBF0` is a candidate item-related handling routine but no verified medal-value table has been found yet. Do not label the extend threshold table as a medal table.
3. **Trace bullet-cancel mechanics** and whether canceled bullets award points or spawn roses in PS2 Arrange; existing `0x0012F...` rank callsites are promising, but the event trigger is not yet verified.
4. **Compare rank frames** on the SH-3 and EE side using matching player/event tests once console/emulator access returns, avoiding assumptions about identical formula scales.
5. **Keep Black Label separate** from Arrange until Kuro's XTC, scoring, and rank behavior are implemented independently; use user-owned arcade data where necessary.

## 7. Reproduce (Windows, macOS, Linux)

Python 3.10+ standard library only. The script is **read-only** and accepts only the exact original Japanese ELF fingerprint, not a prepatched 240p build.

```sh
python audit_rank_scoring.py "SLPM_663.01" --json rank_score_report.json --csv rank_calls.csv
# Or, using the original 3.9 GB ISO (the script reads only the embedded ELF):
python audit_rank_scoring.py "Ibara (Japan).iso" --json rank_score_report.json --csv rank_calls.csv
python test_audit_rank_scoring.py "SLPM_663.01"
```

Expected: 60 fingerprinted instructions, 56 direct JALs to rank down, 2 direct JALs to rank up, and eight unit tests passed. The attached JSON was created from both extracted ELF and full ISO, with matching analyses apart from source type.

**No original ISO, game executable, ROM, game art, or third-party generated recompilation source is distributed here. No game patches are included.**
