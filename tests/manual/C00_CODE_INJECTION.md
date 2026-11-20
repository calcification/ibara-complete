# C00 — injected-code smoke test + savestates for field discovery

**Goal:** prove that compiled EE code can be injected into retail Ibara and run every frame without changing
gameplay, and collect savestates that let us locate the PS2 fields BL features need.
**Status:** PENDING (never run).

## Setup

1. Clean ISO/CHD, PCSX2 CRC **420C7FAB**. Use a temporary memory card.
2. Back up any existing `cheats/SLPM-66301_420C7FAB.pnach`, then copy
   `pnach/hooks/h00_smoke/SLPM-66301_420C7FAB.pnach` into PCSX2's `cheats/` folder.
3. Game Properties → Cheats: enable cheats and the single group `C00 HOOK / code-injection smoke test`.
4. Cold boot.

## Part A — smoke test

| Step | Action | Pass |
|---|---|---|
| A1 | Boot to the title | Game boots as in P00 (no crash, no hang) |
| A2 | Debug → Open Debugger → Memory, go to `000C0000` | `49 42 43 58` ('IBCX'), then `01 00 00 00` |
| A3 | Start Arcade stage 1, play 30 s | `000C0008` (u32) keeps increasing while playing |
| A4 | Shoot an enemy | `000C000C` equals the P1 score word at `0044C600` |
| A5 | Play Arrange stage 1 briefly | same as A3; gameplay identical to P00 |
| A6 | Disassembly at `0012E62C` | `jal 0x000C0010` |

**Fail cases to report:** crash/freeze (note when), counter stuck at 0 (hook not reached or patch not applied),
garbage at `000C0000` before the game starts (cave used by something else).

## Part B — savestates (PCSX2: F1 saves to the current slot, F2 changes slot)

Disable C00 for these (cheats off, cold boot) so the cave check sees the game's own RAM. Name/rename each
file as listed; they're in PCSX2's `sstates/` folder.

| File | Situation |
|---|---|
| `title.p2s` | title screen |
| `arcade_s1.p2s` | Arcade stage 1, a few seconds in |
| `arrange_s1.p2s` | Arrange stage 1, a few seconds in |
| `x_left.p2s`, `x_mid.p2s`, `x_right.p2s` | Arcade stage 1, P1 ship held at far left / centre / far right, same height, not shooting |
| `y_low.p2s`, `y_mid.p2s`, `y_high.p2s` | ship at bottom / middle / top, same horizontal place |
| `shot_up1.p2s`, `shot_up2.p2s` | not pressing anything |
| `shot_dn1.p2s`, `shot_dn2.p2s` | holding the shot button (for > 1 s) |
| `t1.p2s`, `t2.p2s`, `t3.p2s` | ship parked, three moments ~2 s apart (camera scroll) |

Then (Claude or you):

```bash
python3 scripts/p2s_tools.py cave title.p2s arcade_s1.p2s arrange_s1.p2s
python3 scripts/p2s_tools.py find x_left.p2s=0 x_mid.p2s=1 x_right.p2s=2 --range 0044C380:0044C610
python3 scripts/p2s_tools.py find y_low.p2s=0 y_mid.p2s=1 y_high.p2s=2 --range 0044C380:0044C610
python3 scripts/p2s_tools.py find shot_up1.p2s=0 shot_up2.p2s=0 shot_dn1.p2s=1 shot_dn2.p2s=1 --relation group --types u16,u32
python3 scripts/p2s_tools.py find t1.p2s=0 t2.p2s=1 t3.p2s=2 --range 00300000:00500000 --types s32,fx16
```

Savestates contain game RAM: keep them local, do not commit them.
