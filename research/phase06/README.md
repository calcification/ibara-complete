> **CRITICAL ERRATA (discovered Phase 8):** Some absolute player-record/score addresses below are wrong by +0x10000. Use `docs/ERRATA.md` and the corrected Phase 8+ documents; do not set PCSX2 breakpoints for the superseded addresses. Historical report preserved for provenance.

# Ibara Complete — Phase 6: PS2 Arrange / Ibara Kuro static crosswalk

**Status:** Completed static audit, November 19–20, 2026. **No ISO modifications; no emulator or console tests.**

## Why this phase matters

The retail PS2 executable contains an actual, table-driven player-state dispatcher. We have identified the player-state table and the common action handler used by states 1–9. In parallel, the publicly available `ibara360` sources document a separate, 368-record SH-3 patch set to reproduce PS2 Arrange behavior from *arcade* Ibara. Together these expose where Arrange/Kuro differ, without assuming that SH-3 addresses from the Xbox 360 project are valid PS2 addresses.

## 1. Original PS2 binary: direct evidence

Input was the user's **unmodified** Japanese retail executable, verified SHA-256:

`263d3079dee66af82815219351553075340a4d9f42aceaa7bb8ef2bfb812ffac`

| Confirmed original EE address | Static evidence | Confidence |
|---|---|---|
| `0x00212F40` | Start of a 33-entry (index 0 through 32) code-pointer table | Byte-for-byte verified |
| `0x00139C80`, `0x00139CD0` | Two paths compute `0x00212F40 + 4 * player_state` and `jr $v0` | Verified instructions, runtime selection not exercised |
| `0x00139850` | Handler for player states **1–9** (9 identical table entries) | Byte-for-byte verified |
| `0x00139B20` | Handler for states **0, 10–15** | Byte-for-byte verified |
| `0x00139050` | Handler for states **16–31** | Byte-for-byte verified |
| `0x00138F60` | Handler for state **32** | Byte-for-byte verified |
| `0x0013987C–0x0013988C` | MIPS arithmetic computes a per-player stride of `0x290` bytes | Verified instruction sequence |
| `0x001398E4` | Reads an input bitfield and tests mask `0x40` | Verified instruction |
| `0x001399A0` | Reads an input bitfield and tests mask `0x80` | Verified instruction |
| `0x00139A58` | Reads an input bitfield and tests mask `0x100` | Verified instruction |
| `0x001398CC` | Reads `-0x6DAC($gp)` and conditionally branches | Verified instruction; Arrange mode identity requires runtime confirmation |

A `0x290` player-record stride starts from base `0x0045C380`; the state field is accessed through the per-player base plus eight bytes, near `0x00139CB0`. These are **PS2 EE addresses only**, not arcade SH-3 addresses. The meaning of each control bit is informed by source comments in the external project but would still benefit from input/breakpoint tests.

### Why disassembly alone initially hid the function

There are zero direct `JAL` instructions to `0x00139850`. That does **not** mean it is unreachable. Nine consecutive entries of the function-pointer table point at it, and both dispatch paths load an address from that table and perform `jr $v0`. Direct-call xref scanners would not see this call path.

### Action routine callees

The verified `0x00139850` routine contains the following direct calls:

| Callsite | Target |
|---|---|
| `0x001398BC` | `0x0013B510` |
| `0x001398C4` | `0x0013B2F0` |
| `0x00139994` | `0x001370E0` |
| `0x00139A44` | `0x001370E0` |
| `0x00139A4C` | `0x0013AFC0` |
| `0x00139AB4` | `0x001370E0` |

These are *callees*, not yet labeled algorithms. Avoid naming them "subweapon selection" or "bomb effect" without inspecting their bodies and comparing runtime behavior. The common handler does show distinct paths for flags `0x40`, `0x80`, `0x100` and mode-conditional logic.

## 2. What ibara360 actually proves, and what it does not

The external project's sources provide a valuable comparison:

- `gen/ibaraarr/arrange_patch.c` contains **368 patch records**: one 19,932-byte injected SH-3 code/state block and **367 additional SH-3 patch records** amounting to **1,474 bytes**. Many are address/function-pointer detours rather than full subroutine replacements. This is a deterministic count from the publicly available patch manifest; it is **not** 368 patches for the PS2 executable.
- Its `arrange_patch.h` declares Arrange work-RAM state for subweapon, formation, aim-lock, rank handling, rose values, bombs and related systems. These are **arcade SH-3 addresses `0x0C...`**, wholly separate from the retail PS2 EE MIPS layout.
- The author documents recreating PS2 Arrange as patches over the original arcade game, **not** repurposing Kuro's arcade program.
- `gadgets.c` documents the **Kuro-specific Xtreme Terror Counter (XTC)**: player-record fields `+0x280` / `+0x284` / `+0x270`, bullet-graze testing at arcade `0x0C06EF50`, and rank-dependent graze geometry. No evidence in the retail PS2 executable provided here establishes that these Kuro-specific systems already exist as native code.
- `gadgets.c` reports original Ibara arcade player-record stride `0x280`, Kuro arcade stride **`0x2A0`**; we independently derive the **PS2 native `0x290`** stride. These structurally different records make direct transplanting of raw state offsets unsafe.
- Kuro arcade rank is read by ibara360 at `0x0C297A3C`; original arcade Ibara rank at `0x0C27DFF8`. These *differing* addresses are on the emulated arcade side, not candidate offsets for PS2.

**Source links:**

- https://github.com/PaulAtreides67/ibara360/blob/main/gen/ibaraarr/arrange_patch.c
- https://github.com/PaulAtreides67/ibara360/blob/main/gen/ibaraarr/arrange_patch.h
- https://github.com/PaulAtreides67/ibara360/blob/main/host/xsdk/ibara360/source/gadgets.c
- https://github.com/PaulAtreides67/ibara360/blob/main/host/xsdk/ibara360/source/main.c

## 3. Crosswalk: existing PS2 functionality versus missing Kuro systems

| Area | Reuse the PS2 engine? | Evidence, remaining work |
|---|---|---|
| Existing original/Arrange menus and UI | **Yes, as-is** | Earlier Phase 4 located the mode selector; add Black Label separately and preserve both retail modes |
| Input dispatch / controller handling | **Strong candidate** | Player-state table and masks validated here; map actual bindings before changing semantics |
| Player records / movements | **Partial candidate** | Native PS2 `0x290` stride, original arcade `0x280`, Kuro arcade `0x2A0` — remap fields rather than copy records |
| Subweapon selection / formations | **Partial candidate** | PS2 native routine `0x139850` has distinct input paths; compare actual behaviors and Kuro stock model |
| Rank and scoring | **Requires replacement/extension** | SH-3 Arrange manifest includes rank detours; Kuro rank resides at distinct arcade addresses; native PS2 rank functions not yet mapped |
| XTC graze / counter / timer | **Requires new logic** | Kuro source identifies graze and timer behavior; not shown present in native PS2 game |
| Kuro-specific bosses / patterns / enemy art | **Unresolved / likely substantial** | PS2 ISO holds retail original+Arrange data, not established to include Kuro arcade sprites, logic or patterns |
| Sound and 240p output | **Preserve retail base** | Proven existing PS2 facilities; a fully new Kuro mode needs behavior-specific sound and graphics assets |

The preservation goal is *three authentic modes*. A cosmetic approximation of Kuro based on Arrange settings would not meet that goal.

## 4. Next work that needs no Phase 3/4 tests

1. Build a **PS2 EE static function inventory** for rank/scoring, starting from the native Arrange player handler and its callers. Inspect the six outgoing callsites and the per-player state machine. Verify candidate functions against stored MIPS words.
2. Add **Kuro requirements** by subsystem, using the existing Xbox 360 sources as a behavioral reference but **without copying Xbox 360 binaries or conflating SH-3 addresses with EE addresses**.
3. Produce a small, separately compiled EE MIPS test library for one isolated behavior (e.g., XTC counter arithmetic) that can be unit-tested on a desktop. It will not prove the complete game runs at speed on PS2.
4. In parallel, profile CV1000 VRAM from authentic gameplay traces before committing to the sparse-VRAM architecture. If native conversion requires Kuro-only ROM assets, the patcher must clearly request a user-supplied `ibarablk` set.

**Decision:** For arcade accuracy, a small Kuro prototype built on retail frontend + native rendering and ported game systems remains a longer-term goal. Reusing PS2 Arrange as a source of reusable interfaces is good; making Kuro by changing only Arrange options is not credible.

## 5. Running the audit (no boot test required)

Requires **Python 3.8+**, standard library only. It makes no changes to either the ISO or ELF.

```bash
python audit_arrange_dispatch.py "Ibara (Japan).iso" --json dispatch.json --csv dispatch.csv
```

Or with a directly extracted ELF:

```bash
python audit_arrange_dispatch.py SLPM_663.01 --json dispatch.json --csv dispatch.csv
```

The source must match the verified unmodified Japanese retail binary by SHA-256. A previously patched 240p executable will not pass strict verification; always use the original. Works on Windows, macOS and Linux. An alternate `--allow-variant` flag is for auditing a known alternate revision, but it still refuses to mark changed instruction anchors as matching the retail version.

### Safety and provenance

The project here ships only original analysis code and metadata. No copyrighted PS2/arcade executable, ROM, disc texture or game binary is distributed. The upstream `ibara360` root currently has no obvious permissive license in the inspected files; **seek explicit authorization before incorporating and redistributing its recompiled C**. The PS2 retail ISO and Kuro arcade dumps are independent game data sources.

## 6. Reproducible tests

`test_audit.py` contains five unit tests, including detection of an altered instruction and a truncated input. Run with your legally owned, extracted **unmodified** executable:

```bash
# macOS/Linux
IBARA_ORIGINAL_ELF=SLPM_663.01 python test_audit.py -v

# Windows PowerShell
$env:IBARA_ORIGINAL_ELF = "SLPM_663.01"
python test_audit.py -v
```

In the absence of that ELF the binary-specific tests report a skip rather than giving a false failure. Tests were run against the retail executable in the development environment; all five passed. The same audit on the complete user's original ISO also passed. **No runtime game logic or gameplay was exercised.**

## 7. Future PCSX2 breakpoint plan (not required for this phase)

When convenient, the following addresses would validate the static interpretation:

- `0x00139C80`, `0x00139CD0`: inspect player index, state value, computed function pointer.
- `0x00139850`: observe active state `1..9`, check `$gp` and the mode flag at `-0x6DAC($gp)`.
- `0x001398E4`, `0x001399A0`, `0x00139A58`: inspect input bitfield `+0x24E` and the individual `0x40 / 0x80 / 0x100` paths.
- `0x001398BC`, `0x001398C4`: verify whether helper calls affect stock, animation, or input state.

These are **planned observational breakpoints**, not tested hooks, and there is no patched executable in this phase.
