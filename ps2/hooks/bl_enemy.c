/* Black Label enemy rules for the PS2 engine (BLACK LABEL build only).
 *
 * bl_fire_timer replaces the retail enemy fire timer 0x00122120 (arcade 0C0A9E40, BL 0C0BC1B0; 217 PS2 call
 * sites). Retail: the part's counter (+0x9B) counts up while the part may fire (flags & 0x100) and fires
 * (returns 1, counter reset) once it reaches  base + factor * (rank >> 16) / 256.  BL makes the same test with a
 * harder rank: rank - stage * ((k << 18) + 0x40000), floored at 0, where stage is BL's stage byte (2..7) and k the
 * settings byte at 0C234C04 (3 on default settings). Behaviour written from those facts (MAME traces and the
 * Phase 11/12 pairing), not translated code. Entered with `j` from the retail entry, so it returns straight to
 * the retail caller; it is a leaf that touches only temporaries.
 */
#include "ibara_ps2.h"

#ifndef BL_FIRE_K
#define BL_FIRE_K 3u
#endif
#define PS2_STAGE_COUNT 0x00338E9Cu /* $gp-28244: 1 opening, 2 stage 1, 3 stage 2 ... = BL's stage byte */

u32 bl_fire_timer(u32 part, u32 factor, u32 base)
{
	u32 rank, sub, cnt;

	if (!(EE_RAM(u32, part) & 0x100u))
		return 0;
	cnt = (u8)(EE_RAM(u8, part + 0x9B) + 1);
	EE_RAM(u8, part + 0x9B) = (u8)cnt;
	rank = EE_RAM(u32, PS2_RANK_INV);
	sub = EE_RAM(u8, PS2_STAGE_COUNT) * ((BL_FIRE_K << 18) + 0x40000u);
	rank = rank >= sub ? rank - sub : 0;
	if (cnt < (base & 0xFFFFu) + (((factor & 0xFFFFu) * (rank >> 16)) >> 8))
		return 0;
	EE_RAM(u8, part + 0x9B) = 0;
	return 1;
}
