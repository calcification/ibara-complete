/* Ibara (Japan) SLPM-66301, PCSX2 CRC 420C7FAB: EE addresses used by injected hook code.
 *
 * Every symbol carries its evidence level. Only STATIC_VERIFIED values were read from the clean retail
 * ELF by this repository's phase audits; RUNTIME_PENDING values are inferences that must be confirmed in
 * PCSX2 (debugger or savestate eeMemory dump) before any hook that depends on them is enabled.
 * scripts/build_ee_hooks.py refuses to emit an enabled PNACH group whose hook lists a RUNTIME_PENDING
 * dependency (see HOOKS[...]['requires']).
 *
 * All addresses are PS2 EE (MIPS, little-endian). Arcade SH-3 addresses (0C......) never belong here.
 */
#ifndef IBARA_PS2_H
#define IBARA_PS2_H

typedef unsigned char u8;
typedef signed char s8;
typedef unsigned short u16;
typedef short s16;
typedef unsigned int u32;
typedef int s32;

#define EE_RAM(type, addr) (*(volatile type *)(addr))

/* ---- STATIC_VERIFIED (research/phase06..10, original ELF sha256 263d3079...) ---- */
#define PS2_PLAYER_BASE      0x0044C380u /* P1 record (Phase 8 corrected) */
#define PS2_PLAYER_STRIDE    0x290u      /* arcade Ibara 0x280, Kuro BL 0x2A0 */
#define PS2_PLAYER_SCORE     0x280u      /* P1 score 0x0044C600 = base + 0x280 */
#define PS2_RANK_INV         0x00338EB4u /* stored rank: 0x00FFFFFF easiest .. 0 hardest */
#define PS2_SHOTS_BASE       0x0044EA40u /* player-side projectile pool, 128 x 0x50 per side */
#define PS2_SHOT_STRIDE      0x50u
#define PS2_BULLETS_BASE     0x004682ECu /* opposing projectile pool used by 0x0012AC60 */
#define PS2_BULLET_STRIDE    0x54u       /* same stride as arcade's 256 x 0x54 enemy bullet pool */
#define PS2_ITEMS_BASE       0x00453A40u /* 256 x 0x58 */
#define PS2_FN_COLLIDE_CANCEL 0x0012AC60u /* per-frame collision pass, called from 0x0012E62C */
#define PS2_SITE_FRAME_COLLIDE 0x0012E62Cu /* jal 0x0012AC60 (word 0x0C04AB18) */

/* ---- RUNTIME_PENDING (inferred from the arcade layout; confirm before use) ---- */
/* Enemy bullet record, by analogy with the arcade pool (same 0x54 stride):
 *   +0x00 u32 flags (0x10000000 can hit the player, 0x00004000 long-bullet segment)
 *   +0x28 s32 x (16.16, screen), +0x2C s32 y (16.16, world: subtract the camera) */
#define PS2_BULLET_FLAGS     0x00u
#define PS2_BULLET_X         0x28u
#define PS2_BULLET_Y         0x2Cu
#define PS2_BULLET_COUNT     256u
#define BULLET_CAN_HIT       0x10000000u
#define BULLET_SEGMENT       0x00004000u
/* Player record fields still to be located on PS2 (arcade Ibara offsets in brackets):
 *   flags +0x00 [+0x00] (0x04000000 can be hit), x/y 16.16 [unknown], camera global [0C3929E0] */
#define PS2_PLAYER_FLAGS     0x00u
#define PLAYER_CAN_BE_HIT    0x04000000u
#define PS2_PLAYER_X         0xFFFFFFFFu /* UNKNOWN: find in PCSX2 (moves with the stick) */
#define PS2_PLAYER_Y         0xFFFFFFFFu /* UNKNOWN */
#define PS2_CAMERA_Y         0xFFFFFFFFu /* UNKNOWN: global s32 16.16 subtracted from bullet y */
#define PS2_PAD_HELD         0xFFFFFFFFu /* UNKNOWN: P1 held-button word as the game reads it */

/* Code cave for injected hooks. 0x000C0000-0x000FFFFF lies below the ELF load address (0x00100000) and
 * above the EE kernel's 512 KiB; PS2 cheat/hack code commonly lives here, but the game or its IOP loader
 * could still use it. RUNTIME_PENDING: confirm the whole range reads zero in savestates taken at the
 * title, in Arcade and in Arrange (scripts/build_ee_hooks.py --check-ram eeMemory.bin). */
#define PS2_CAVE_BASE        0x000C0000u
#define PS2_CAVE_END         0x00100000u

#endif
