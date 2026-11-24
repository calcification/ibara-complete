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

/* BL bullet cancel after bosses and mid-bosses (F10). BL's main loop (0C06C630) runs its cancel-all (0C0BC310,
 * BL-only) while the counter 0C2B07FC is non-zero; ~25 death paths set it to 16 (no score for the bullets).
 * MAME, stages 1-6 (write tap on the counter + per-frame kill log: HP from > 0 to 0, alive or freed): every write
 * but one follows the kill of one particular part, given here as (stage byte, type, subtype). The part types and
 * subtypes are the same on PS2 (PCSX2 kill log, same stages), so each frame the PS2 pool is checked for those
 * kills and every enemy bullet record is cleared for 16 frames. HOLD parts keep BL's counter at 16 for their whole
 * death animation (stage-1 type 11 tanks: 141 frames, as on PS2; stage-1 boss core: ~216), so they re-arm it
 * every frame while alive with HP 0. Not covered: one stage-5 write with no part kill (MAME frame 55448).
 * Called every game frame from xtc_frame (KURO only). research/phase17. */
#define EN_BASE   0x0045A840u /* 192 x 0xB4: +00 flags (bit 31 alive), +04 type, +08 subtype, +3C HP */
#define EN_STRIDE 0xB4u
#define EN_COUNT  192u
#define HOLD      0x80u

static const u8 bc_trig[][4] = { /* stage byte (2 = stage 1), type, subtype, HOLD */
	{2, 11, 0, HOLD}, {2, 11, 1, HOLD}, {2, 5, 0, HOLD},                       /* stage 1 */
	{3, 34, 0, 0}, {3, 33, 0, 0},                                              /* stage 2 mid-bosses */
	{3, 45, 0x3D, 0}, {3, 45, 0x31, 0}, {3, 45, 0x2A, 0}, {3, 45, 0, 0},       /* stage 2 boss */
	{4, 48, 4, 0}, {4, 48, 7, 0}, {4, 48, 0, 0}, {4, 51, 2, 0}, {4, 51, 0, 0}, /* stage 3 */
	{5, 41, 0, 0}, {5, 42, 0, 0},                                              /* stage 4 */
	{6, 65, 0, 0}, {6, 65, 6, 0},                                              /* stage 5 */
	{7, 69, 0, 0}, {7, 74, 0, 0}, {7, 74, 2, 0},                               /* stage 6 */
};
static u16 bc_hp[EN_COUNT]; /* HP last frame, 0 when not alive */
u32 bc_left; /* frames of clearing left (read by the BL_MIDLOG test logger) */

void bl_boss_cancel_frame(void)
{
	const u32 stage = EE_RAM(u8, PS2_STAGE_COUNT);
	u32 i, k;
	for (i = 0; i < EN_COUNT; i++) {
		const u32 a = EN_BASE + i * EN_STRIDE;
		const u32 alive = EE_RAM(u32, a) & 0x80000000u;
		const u32 hp = EE_RAM(u16, a + 0x3C);
		if (hp == 0u && (bc_hp[i] || alive)) {
			const u32 type = EE_RAM(u32, a + 4), sub = EE_RAM(u32, a + 8);
			for (k = 0; k < sizeof bc_trig / sizeof bc_trig[0]; k++)
				if (bc_trig[k][0] == stage && bc_trig[k][1] == type && bc_trig[k][2] == sub &&
				    (bc_hp[i] || (alive && (bc_trig[k][3] & HOLD))))
					bc_left = 16u;
		}
		bc_hp[i] = alive ? (u16)hp : 0u;
	}
	if (!bc_left)
		return;
	bc_left--;
	for (i = 0; i < 256u; i++) {
		const u32 a = PS2_BULLETS_BASE + i * PS2_BULLET_STRIDE;
		if (EE_RAM(u32, a) & BULLET_CAN_HIT)
			EE_RAM(u32, a) = 0u;
	}
}

/* BL stage-5 script (research/phase25). The stage scripts are time-ordered records (time, type, position,
 * subtype, flags) and commands (0xFFxx). BL's stage-5 script (0C202142) has six more type-52 waves than the PS2
 * script (0x001ECF80, pointed to by stage 5's table word 0x001F1850): MAME and PCSX2 spawn logs show 9 waves vs 3,
 * and the scripts are otherwise the same records. The PS2 script cannot grow in place, so KURO builds a copy here
 * from the retail words (up to the end command FF03 7FFF) with BL's six records inserted after the third wave, and
 * the runtime table points 0x001F1850 at it. If the retail words are not the expected ones, the copy is the plain
 * retail script. Leaf, temporaries only. */
#define S5_SCRIPT 0x001ECF80u
#define S5_INSERT 0x001ED01Au /* after the record (0x188, 52, 0x240, 2, 0x4000) */
#define S5_END    0x001ED0B6u /* past FF03 7FFF */
static const u16 bl_s5_waves[30] = {
	0x0348, 0x0034, 0x0200, 0x0002, 0x4000, 0x04B8, 0x0034, 0x01C0, 0x0002, 0x4000,
	0x0578, 0x0034, 0x0240, 0x0002, 0x4000, 0x07A8, 0x0034, 0x01C0, 0x0002, 0x4000,
	0x07A8, 0x0034, 0x0240, 0x0002, 0x4000, 0x0898, 0x0034, 0x01E0, 0x0002, 0x4000,
};
u16 bl_s5_script[(S5_END - S5_SCRIPT) / 2u + 30u] __attribute__((aligned(16)));
u32 bl_s5_ready;

void bl_scripts_build(void)
{
	const volatile u16 *src = (const volatile u16 *)S5_SCRIPT;
	const u32 n_ins = (S5_INSERT - S5_SCRIPT) / 2u, n_all = (S5_END - S5_SCRIPT) / 2u;
	const u32 ok = src[n_ins - 5u] == 0x0188u && src[n_ins - 4u] == 0x0034u && src[n_ins] == 0x08C0u &&
		       src[n_all - 2u] == 0xFF03u && src[n_all - 1u] == 0x7FFFu;
	u32 i, k = 0;

	for (i = 0; i < n_ins; i++)
		bl_s5_script[k++] = src[i];
	if (ok)
		for (i = 0; i < 30u; i++)
			bl_s5_script[k++] = bl_s5_waves[i];
	for (i = n_ins; i < n_all; i++)
		bl_s5_script[k++] = src[i];
	bl_s5_ready = 1;
}
