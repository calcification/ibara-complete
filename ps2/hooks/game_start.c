/* K62: a game starts clean (research/phase44).
 *
 * Some state outlives the game it belongs to and changes the next one:
 *   - Practice's GAME START skips the stage's item initialiser 0x00132640, so the item drop counters
 *     (0x00338E54/55/58/59/5C), the drop tables 0x00495120-0x0049513F and any items still on screen at RETURN MENU
 *     carry into the next Practice game;
 *   - our boss bullet-cancel tracker (bl_enemy.c) keeps last frame's HP per enemy slot and its clearing timer;
 *   - the XTC graze test (xtc.c) alternates sides each update and keeps its phase.
 * At the first game update of each game (the update path starts at 0x0012E5CC, `jal 0x00138CD0`) these are reset
 * to what the item initialiser and a fresh start leave. Not in attract mode, whose demo must play as recorded.
 * kuro_frame clears the latch whenever no game is running (MAIN_STATE != 5). */
#include "ibara_ps2.h"

#define MAIN_STATE 0x00338B08u /* 5: a game is running */
#define ATTRACT    0x00338E7Cu /* u8 */
#define ITEMS_STRIDE 0x58u
#define ITEMS_COUNT  256u

void xtc_reset(void);
void bl_enemy_reset(void);
#ifdef REPLAY_BUILD
void replay_update(void);
#else
void rpl_update(void);
#endif

static u8 gs_started;

void game_start_frame(void)
{
	if (EE_RAM(u32, MAIN_STATE) != 5u)
		gs_started = 0;
}

/* every slot (all) or every inactive slot: objects keep fields their spawn code does not set (research/phase44) */
static void clear_pool(u32 base, u32 stride, u32 count, u32 all)
{
	u32 i, w;
	for (i = 0; i < count; i++, base += stride)
		if (all || !(EE_RAM(u32, base) & 0x80000000u))
			for (w = 0; w < stride; w += 4u)
				EE_RAM(u32, base + w) = 0;
}

/* also rpl.c, where a Noir replay starts (Stage 1's first update): the player may already be firing as the select
 * screen hands over, and a playback skips the select screen, so both sides start Stage 1 without leftovers */
void game_start_reset(void)
{
	u32 i;
	/* no shot, item or bullet exists at a game's first update; items can survive RETURN MENU */
	clear_pool(PS2_SHOTS_BASE, PS2_SHOT_STRIDE, 256u, 1u);
	clear_pool(PS2_BULLETS_BASE, PS2_BULLET_STRIDE, PS2_BULLET_COUNT, 1u);
	clear_pool(0x0044D6C0u, 0x34u, 96u, 1u);   /* pod shots (48 per side) */
	clear_pool(0x0045A840u, 0xB4u, 192u, 0u);   /* enemies: inactive slots */
	clear_pool(0x00468340u, 0x3Cu, 532u, 0u);   /* the pool after the bullets (effects): inactive slots */
	for (i = 0; i < ITEMS_COUNT; i++) /* as 0x00132640: every item slot's flags word */
		EE_RAM(u32, PS2_ITEMS_BASE + i * ITEMS_STRIDE) = 0;
	EE_RAM(u8, 0x00338E54u) = EE_RAM(u8, 0x00338E55u) = EE_RAM(u8, 0x00338E58u) = 0;
	EE_RAM(u8, 0x00338E59u) = EE_RAM(u8, 0x00338E5Cu) = 0;
	for (i = 0; i < 32u; i++)
		EE_RAM(u8, 0x00495120u + i) = 0;
	bl_enemy_reset();
	xtc_reset();
}

void game_update(void)
{
	if (EE_RAM(u32, MAIN_STATE) != 5u || EE_RAM(u8, ATTRACT))
		return;
	if (!gs_started) {
		gs_started = 1;
		game_start_reset();
	}
#ifdef REPLAY_BUILD
	replay_update();
#else
	rpl_update(); /* records every game; plays one back when asked */
#endif
}

/* Replaces `jal 0x00138CD0` at 0x0012E5CC: ra (0x0012E5D4) is set by our jal and kept for the tail call. Saves the
 * callee-saved registers with 128-bit sq (our C may use them with 32-bit saves) and the argument, result and
 * temporary registers the update path might still hold. MAY_UPDATE decides first: 0 skips this update and takes the
 * retail draw-only path 0x0012E1EC (the loaders run; the input and the stage clock wait), as a replay holds for a
 * load that finished sooner in its recording (rpl.c, loader gates). */
#if defined(RP_CONTROLLER_SYNC)
#define MAY_UPDATE "replay_controller_may_update"
#elif defined(RPL_DRIFT_PROBE)
#define MAY_UPDATE "rpl_drift_may_update"
#else
#define MAY_UPDATE "rpl_may_update"
#endif
__asm__(
	".set push\n.set noreorder\n.set noat\n"
	".globl game_update_entry\n"
	"game_update_entry:\n"
	"	addiu $sp,$sp,-0x150\n"
	"	sq $ra,0x00($sp)\n"
	"	sq $s0,0x10($sp)\n"
	"	sq $s1,0x20($sp)\n"
	"	sq $s2,0x30($sp)\n"
	"	sq $s3,0x40($sp)\n"
	"	sq $s4,0x50($sp)\n"
	"	sq $s5,0x60($sp)\n"
	"	sq $s6,0x70($sp)\n"
	"	sq $s7,0x80($sp)\n"
	"	sq $fp,0x90($sp)\n"
	"	sq $gp,0xA0($sp)\n"
	"	sq $a0,0xB0($sp)\n"
	"	sq $a1,0xC0($sp)\n"
	"	sq $a2,0xD0($sp)\n"
	"	sq $a3,0xE0($sp)\n"
	"	sq $v0,0xF0($sp)\n"
	"	sq $v1,0x100($sp)\n"
	"	sq $t0,0x110($sp)\n"
	"	sq $t1,0x120($sp)\n"
	"	sq $t2,0x130($sp)\n"
	"	jal " MAY_UPDATE "\n"
	"	nop\n"
	"	beqz $v0,1f\n"
	"	sw $v0,0x140($sp)\n"
	"	jal game_update\n"
	"	nop\n"
	"1:\n"
	"	lq $t1,0x120($sp)\n"
	"	lq $t0,0x110($sp)\n"
	"	lq $v1,0x100($sp)\n"
	"	lq $v0,0xF0($sp)\n"
	"	lq $a3,0xE0($sp)\n"
	"	lq $a2,0xD0($sp)\n"
	"	lq $a1,0xC0($sp)\n"
	"	lq $a0,0xB0($sp)\n"
	"	lq $gp,0xA0($sp)\n"
	"	lq $fp,0x90($sp)\n"
	"	lq $s7,0x80($sp)\n"
	"	lq $s6,0x70($sp)\n"
	"	lq $s5,0x60($sp)\n"
	"	lq $s4,0x50($sp)\n"
	"	lq $s3,0x40($sp)\n"
	"	lq $s2,0x30($sp)\n"
	"	lq $s1,0x20($sp)\n"
	"	lq $s0,0x10($sp)\n"
	"	lq $ra,0x00($sp)\n"
	"	lw $t2,0x140($sp)\n"
	"	beqz $t2,2f\n"
	"	lq $t2,0x130($sp)\n"
	"	j 0x00138CD0\n"
	"	addiu $sp,$sp,0x150\n"
	"2:\n"
	"	j 0x0012E1EC\n"
	"	addiu $sp,$sp,0x150\n"
	".set pop\n");
