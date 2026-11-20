# Errata to Ibara Complete Phases 6–7 (PS2 retail executable)

The previous Phase 6 and Phase 7 reports incorrectly resolved an **absolute EE player-record address** by **+0x10000**. These values were documentation errors, not changes to the retail game. They have been checked against the literal `lui` / signed `addiu` pairs in the original `SLPM_663.01`.

| Symbol | Earlier (incorrect) | Verified correction |
|---|---|---|
| 1P player record | `0x0045C380` | `0x0044C380` |
| 2P player record | `0x0045C610` | `0x0044C610` |
| 1P score (+0x280) | `0x0045C600` | `0x0044C600` |
| 2P score (+0x280) | `0x0045C890` | `0x0044C890` |
| 1P next extend (+0x284) | `0x0045C604` | `0x0044C604` |
| 2P next extend (+0x284) | `0x0045C894` | `0x0044C894` |

### Supporting original instructions

- At EE `0x0012A984`: `lui $a0, 0x0045` (word `0x3C040045`).
- At EE `0x0012A98C`: `addiu $a0, $a0, -0x3C80` (word `0x2484C380`).
- Signed addition makes `0x00450000 - 0x3C80 = 0x0044C380`.
- At EE `0x0012EC4C` / `0x0012EC50`, the same construction produces `0x0044C600` as the scoring word base (`lui $a1,0x45`; `addiu $a1,$a1,-0x3A00`).
- Two-player stride `0x290` remains correct.

**Do not use the earlier Phase 6–7 memory addresses in patches or live memory watchlists.** Other Phase 6/7 findings are not automatically invalidated, but their absolute address claims should be checked independently before hooking.

### Another Phase 7 clarification

The caller at `0x0012AC18` reaches `0x00134E90`, a helper that returns **the maximum of two 32-bit signed arguments**. Specifically, `slt $at,$a1,$a0` then `movz $a0,$a1,$at` chooses the larger input. The subsequent addition at `0x0012AC24` therefore uses the greater of the two values loaded from object offsets `+0x40` / `+0x44`. There is no evidence this helper is a medal multiplier.

This errata was established by direct disassembly of the user's original 2006 ELF. No gameplay patches were applied.
