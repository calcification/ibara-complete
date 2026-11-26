# Phase 38 — Homing pods with no target (Claude, 26 November 2026; K61)

Follows Codex's phase 36: with no target, BL's homing pods use formation headings; the PS2 points all three at 0.

## BL (MAME)

`bl_homing_headings.lua`, stage-6 checkpoint, homing selected with the weapon-change input, enemy pool cleared every
frame, each stick state held 60 frames. BL's P1 pod records are at 0x0C2974C8 (stride 48; pod kind at +4 / +16,
heading word at +38).

| Stick | Pod 0 | Pod 1 | Pod 2 (centre) |
|---|---:|---:|---:|
| none / down | 288 | 224 | 0 |
| up | 288 | 224 | 256 |
| left / right | 288 | 224 | 128 / 384 |
| up-left / up-right | 288 | 224 | 192 / 320 |
| down-left / down-right | 288 | 224 | 64 / 448 |

The outer pods never change; the centre pod points opposite the stick (headings of 512).

## Noir (K61)

`ps2/hooks/bl_enemy.c` `bl_homing_idle`: the PS2's no-target branch (0x00134364 `move v1,zero`, `b 0x001343B4`, delay
`sh v1,38(s0)`) gets `j bl_homing_idle` at 0x00134368 (Noir runtime word). For the homing weapon (+0x270 = 3) it
writes 288 / 224 to pods 0 / 1 and the centre pod's heading from the stick bits (+0x24C: up 1, down 2, left 4,
right 8). The target path (a target found) is untouched.

PCSX2 test (`rose_probe.c` `BL_HOMING_DIRTEST` with `BL_FORCE_POD_WEAPON=3`: no enemies, the same nine stick states):
all nine heading triples equal BL's. Codex's phase-36 stationary fallback (same headings when not moving) raised
Noir's live stage-2 homing launches from 373 to 441 (BL 549) and the no-target case from 513 to 1,159 (BL 1,160).
Remaining live gap: Codex's phase-36 follow-up (projectile lifetime, target selection).
