# Research phase index

| Phase | Location | Findings | Validated by |
|---|---|---|---|
| 01 | `research/phase01` | ELF format, original menu labels, script references | original ELF metadata |
| 02 | `research/phase02` | PDM/TBL parsing, free sectors, complete TIM2/audio catalog | original ISO layout and CRCs |
| 03 | `research/phase03` | In-place ISO9660 injection and synthetic ELF | byte/CRC offline; **boot pending** |
| 04 | `research/phase04` | selector code, 5 menu branches, dormant texture button | opcode/artwork only; **runtime pending** |
| 05 | `research/phase05` | sparse CV1000 VRAM/NAND cache prototype | host C/Python tests, MIPS III object (not linked) |
| 06 | `research/phase06` | EE player-state pointer table | fingerprinted MIPS; **read errata** |
| 07 | `research/phase07` | inverted rank & extend thresholds | fingerprinted MIPS; **read errata** |
| 08 | `research/phase08` | item-pickup dispatcher and 19 medals | fingerprinted MIPS; corrected player addresses |
| 09 | `research/phase09` | collision-to-item conversion, rose multiplier | fingerprinted MIPS; factor-at-spawn cap only |
| 10 | `research/phase10` | rose merge helper, factor accumulation | fingerprinted MIPS; raw 32-bit arithmetic |

**Warning:** some historical sample JSON reports may contain original errors or old provisional interpretations. Prefer new runs against your clean original revision. For all external research changes, create separate follow-up reports with explicit confidence qualifiers.
