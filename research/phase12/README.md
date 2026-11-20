# Phase 12 — arcade SH-3 ↔ PS2 EE routine matcher

**Purpose:** for every arcade Ibara routine that Black Label changed (Phase 11: 326 changed, 161
literal-only, 104 removed/rewritten), propose the PS2 MIPS routine that ports it. Those PS2 routines are
where BL behaviour has to be hooked.

**Why it can work:** the PS2 port keeps the arcade's structures (shot stride 0x50, bullet stride 0x54,
2^24 inverted rank, player record 0x290 vs 0x280), so a routine and its port tend to share distinctive
constants and touch the same structures.

| File | Role |
|---|---|
| `mips_funcs.py` | standard-library R5900 extractor: function starts (entry, jal targets, data code pointers, prologues after `jr ra`), calls, lui-built constants, absolute/`$gp` data refs, load/store displacements |
| `xisa_match.py` | idf-weighted constant Jaccard (0.60) + shared-structure Jaccard (0.25) + size agreement (0.15); mutual-best assignment; call-graph propagation; `--anchor SH3=PS2` seeds |

```bash
python3 research/phase12/xisa_match.py /path/to/ibara360 SLPM_663.01 --out research/phase12/out \
    --anchor <arcade>=<ps2> ...
```

`out/arcade_to_ps2.csv` lists, per arcade routine: PS2 candidate, method, score, and its Black Label
status/address from Phase 11. **Candidates only:** confirm each in the PCSX2 debugger before hooking.

## First run on the retail ELF (2026-11-20, SHA-256 `263d3079…`, all 20 phase 1–10 audits PASS)

* The ELF has one RWE segment (code and data interleaved, no symbols), so functions are found by
  **recursive descent** from the entry point, every `jal` word, and data words pointing at prologues;
  `$gp` = `0x0033FCF0` from `.reginfo`. Result: **1,932 PS2 functions**. All 8 PS2 routines named in
  Phases 6–10 are found, and their call lists match those phases exactly (e.g. `0x0012AC60` → `0x00121FC0`
  ×5, `0x00139850` → the six Phase 6 callees).
* Features: constants plus, on the MIPS side, load/store displacements (shared struct field offsets),
  which doubled coverage.
* **246 arcade routines have a PS2 candidate** (202 mutual-best, 44 call-graph), **136 of them in the set
  Black Label touches**. Output: `out/arcade_to_ps2.csv`, `out/summary.json`.

Seed anchors used (semantic, static — confirm in the debugger):

| arcade | PS2 | reason |
|---|---|---|
| `0C05F020` | `0x0012AC60` | the only routine on each side touching player + shot table + bullet pool (PS2 adds Arrange-only branches, hence 5 helper calls vs 1) |
| `0C060D60` | `0x00129DC0` | 12-instruction rank updaters, no constants |
| `0C0A9E40` | `0x00122120` | small rank routines sharing `0x100 / 0xFFFF / 0xFF` |

**Confidence:** candidates. Callee consistency among matches is 72%, but propagation inflates that;
most low-score pairs (< 0.45) are unverified guesses. Coverage of the remaining ~1,090 arcade routines needs
better features (basic-block shape, callers) or debugger-confirmed anchors.

**First anchors to seed tomorrow** (PS2 side verified in Phases 6–10; arcade side to confirm): the
per-frame collision pass `0x0012AC60`, the pickup dispatcher `0x0012FD00`, the item creator `0x001306D0`,
and the rank updaters `0x00129DC0` / `0x00129DF0`.
