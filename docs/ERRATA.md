# Mandatory errata / correction policy

Treat this page as authoritative over older copied phase reports.

1. **Phase 6 and 7 player record base:** `0x0045C380` is WRONG due to signed-MIPS-immediate translation. Use **`0x0044C380`** for P1 record, **`0x0044C600`** for P1 score, with stride **`0x290`**. The Phase 8 audit documents derivation. DO NOT use old addresses in a debugger or patch.
2. **Phase 9 rose scoring model:** the initial `factor` of a spawned Arrange rose may be at most 300. But **merged items can accumulate factors greater than 300**. Phase 10's `rose_points` model and merge helper supersede any old Phase 9 input validation that rejects factor >300.
3. **Phase 4 asset-only button:** it exists in a dormant texture slot, **not** in the running five-entry menu; do not call it a working third menu item.
4. **Phase 3 probe:** magenta is only an intended result if GS display output is configured sufficiently; a black screen **does not** disprove ELF execution. Inspect the EE PC.
5. **Phase 5 MIPS III .o:** compilation of an object proves toolchain targeting only, not a linked PS2 ELF or adequate performance.
6. **Phase 6 and later:** source-derived SH-3 addresses beginning `0x0C` describe the *arcade* CPU, not MIPS EE PS2 addresses.
7. **Baseline:** all fingerprinted reverse-engineering audits assume the **unmodified** Japanese ELF; the already patched progressive 240p build will intentionally fail them.
8. **Unresolved:** numeric player-projectile types 0/1/2/9/10 have not been conclusively mapped to bomb, Hadou, trail, or regular shot. Avoid invented type labels.

Original correction log: [Phase 6–7 errata](PHASE6-7_ORIGINAL_ERRATA.md). When revising an interpretation, include an instruction address, raw opcode evidence, control-flow trace, and whether it is static/dynamic.
