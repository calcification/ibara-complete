## UPDATE: PCSX2-first handoff is now the primary workflow

**Read [`PCSX2_FIRST.md`](PCSX2_FIRST.md) first.** Keep one **unmodified retail ISO/CHD** on the PCSX2 machine and use the tiny `pnach/SLPM-66301_420C7FAB.pnach` for test iterations. The official PCSX2 XOR checksum of the clean retail ELF is **`420C7FAB`**, distinct from the ordinary ELF CRC32 `F9085060`. Runtime patches can be toggled in game properties. `scripts/build_pnach.py` verifies original ELF preimages and generates stand-alone profiles. The 3.66 GB Phase 3/4 ISO builders are optional fallback tests, not required to run the normal patch suite. Do not attribute runtime success to offline fingerprints.

# Handoff for another model / engineer — start here

**Objective:** add a *genuinely authentic* Ibara Kuro / Black Label as a third mode to Japanese PlayStation 2 *Ibara* `SLPM_663.01`, retaining **Arcade**, **Arrange**, existing menus/save behavior, and ultimately native 240p CRT accuracy. Do not settle for an Arrange reskin or falsely claim authenticity.

**Baseline files:** user-owned `Ibara (Japan).iso` (3,932,848,128 bytes; SHA-256 `6e58b52aa5c03d45e413e8473be52a39205095e34a1bd58dae6bd852eb4fb1db`), boot `SLPM_663.01` (2,329,648 bytes; SHA-256 `263d3079dee66af82815219351553075340a4d9f42aceaa7bb8ef2bfb812ffac`). Never commit ISO, retail ELF, arcade ROMs, ripped graphics or sound.

**Phase 1:** ELF32 little-endian MIPS; file segment offset 0x80, EE load at 0x00100000. Retail internal Arcade/Arrange menus and patch opcode signatures mapped. `research/phase01/`.

**Phase 2:** resource archive `IBARAR.PDM` and `IBARAR.TBL`, 1130 entries (1113 TIM2, 16 BG00 audio, 1 SE00). PDM #946: 256×256 indexed menu buttons. `DAMMY1G.DAT` followed by 1,300,000 unused sectors, verified zero in the clean ISO; potential secondary executable storage. `research/phase02/`.

**Phase 3:** builder adds self-authored `KURO_PROBE.ELF` at LBA 500286 and registers `/KURO.ELF;1`; inject leaves retail boot path, probe sets new SYSTEM.CNF pointer at 500287. Full-file offline byte/CRC checks performed. **Neither boot has been observed in PCSX2 nor real hardware.** `research/phase03/`, `tests/fixtures/KURO_PROBE.ELF`.

**Phase 4:** top-level five-item selector around `0x001CA42C`, accept dispatcher `0x001CA798`; Arcade state 2 from `0x001CA800`, Arrange state 9 from `0x001CA824`. Five-entry bounds and graphics descriptor table need expansion. Two unused pointer slots `0x002A90D8`, `0x002A90DC`, subject to live-state validation. Resource #946 has transparent 112×48 slot (112,96)..(224,144); a placeholder button can be injected asset-only but **remains unseen by retail code**. `research/phase04/`.

**Phase 5:** ibara360 Kuro arcade ROM roles (U4 2 MiB, U2 132 MiB, U23/U24 4 MiB each); simulated arcade RAM 8 MiB, virtual CV1000 VRAM 64 MiB; PS2 EE main RAM 32 MiB. Sparse tiled VRAM and NAND cache prototype passes synthetic tests; not integrated into a bootable Kuro program. `research/phase05/`.

**Phase 6:** retail PS2 player-state dispatch table at `0x00212F40`; states 1–9 share handler `0x00139850`; PS2 stride 0x290 vs arcade Ibara 0x280 vs Kuro 0x2A0. `ibara360` Arrange SH-3 patch manifest has 368 records; these are NOT PS2 patch offsets. **Read errata on player addresses.** `research/phase06/`.

**Phase 7:** rank-related EE memory `0x00338EB4`, inverted stored rank; candidate saturating update functions `0x00129DC0`, `0x00129DF0`; 58 direct callsites audited (2 increase, 56 decrease stored value). Extend handler `0x0013AB30` etc. **Read errata.** `research/phase07/`.

**Phase 8:** 8 item *collection* handlers from table `0x0020BF60`; type 3 = medal with verified 19-level 100–10,000 award ladder at `0x0020B100`; type 7 = score/rose item; Arcade and Arrange use different rank deltas. Corrected P1 address `0x0044C380`, score `0x0044C600`. `research/phase08/`.

**Phase 9:** projectile-to-bullet collision path near `0x0012AC60` / `0x0012AE40`, item conversion helper `0x00121FC0`, item creation `0x001306D0` and score collection. Arrange spawned rose scoring: `(10*level+30)*factor` with rank-derived factor min 1, cap 300 **at creation**. Projectile numeric ID semantics remain unverified. `research/phase09/`.

**Phase 10:** distinct 8-entry item *update* table at `0x0020BF00`, type 7 updater `0x00132BC0`, overlap/merge helper `0x0012EA10`, item slots `0x00453A40`, 256 × 0x58. Compatible overlaps increment surviving level by 1 and ADD score factors at `+0x54` (no post-merge 300 cap). At most one success per call. `research/phase10/`.

### Immediate responsibilities

1. **Do not publish a functional Kuro claim.** First run the small **PCSX2 P00–P06 PNACH tests** in [PCSX2_FIRST](PCSX2_FIRST.md), then only the relevant optional ISO-specific B01–B04 tests. Record CRC, active profile, EE memory evidence and PCSX2 version.
2. **Independent review:** reconstruct critical routines in Ghidra/PCSX2; compare raw instructions and delay slots, not merely old AI prose. Audit patched vs original and report mismatches; respect Phase 8+ corrections.
3. **Identify projectile numeric IDs** by tracing writers for projectile `+0x04` and `+0x08`, starting from `0x0011A580`, pool `0x0044EA40`, 128 slots/side, stride 0x50. Map bombs/Hadou/trails only after evidence.
4. **Kuro architecture decision:** independently compare authentic Kuro CV1000 behavior and ROM (user-supplied) against native PS2 systems, with timed input/output traces. Consider faithful native adaptation vs highly optimized recompile; currently neither proven.
5. **Preserve previous video work:** 240p Ibara baseline remains separately maintained at `calcification/cave-ps2-240p`, with minor shimmer unresolved. Re-integrate only after loader and normal game path tests.

### Source hierarchy / caveats

- Raw original MIPS bytes / full ISO structure > reproducible audit script > instruction excerpts > inferred function semantics > illustrative arithmetic > external project's code comments.
- `PaulAtreides67/ibara360` is an *external reference*. Its generated SH-3 code does not belong in this repository and must not be copied blindly or assumed licensed.
- Avoid modifying existing Arcade and Arrange paths while exploring third mode. Keep every test image separate and checksum-guarded.
- All manual boot tests remain **PENDING** until user attaches logs, screenshots or GS dumps.

### Repo structure

`research/phase01..10` contains unchanged phase tools and historical docs (two original docs labeled with errata). `scripts/run_audits.py` reruns static tests against your clean original ISO. `scripts/build_pnach.py` generates zero-ISO-rebuild runtime patch profiles. `scripts/build_test_images.py` remains available only for separate boot/asset ISO experiments. `tests/manual` contains executable test procedures and a result template. `docs/STATUS.md` is the current truth, `docs/ERRATA.md` overrides superseded statements.
