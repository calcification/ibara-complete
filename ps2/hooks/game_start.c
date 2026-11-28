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
#endif

static u8 gs_started;

void game_start_frame(void)
{
	if (EE_RAM(u32, MAIN_STATE) != 5u)
		gs_started = 0;
}

static void game_start_reset(void)
{
	u32 i;
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
#endif
}

/* Replaces `jal 0x00138CD0` at 0x0012E5CC: ra (0x0012E5D4) is set by our jal and kept for the tail call. Saves the
 * callee-saved registers with 128-bit sq (our C may use them with 32-bit saves) and the argument, result and
 * temporary registers the update path might still hold. */
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
#ifdef RP_CONTROLLER_SYNC
	/* Pause before game_update consumes input. The native render-only path
	 * gives the disc and texture loader time to finish the recorded spawn. */
	"	sq $t2,0x130($sp)\n"
	"	jal replay_controller_may_update\n"
	"	nop\n"
	"	beqz $v0,1f\n"
	"	sw $v0,0x140($sp)\n"
	"	jal game_update\n"
	"	nop\n"
	"1:\n"
#else
	"	jal game_update\n"
	"	sq $t2,0x130($sp)\n"
#endif
	"	lq $t2,0x130($sp)\n"
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
#ifdef RP_CONTROLLER_SYNC
	"	lw $t2,0x140($sp)\n"
	"	beqz $t2,2f\n"
	"	lq $t2,0x130($sp)\n"
#endif
	"	j 0x00138CD0\n"
	"	addiu $sp,$sp,0x150\n"
#ifdef RP_CONTROLLER_SYNC
	"2:\n"
	"	j 0x0012E1EC\n"
	"	addiu $sp,$sp,0x150\n"
#endif
	".set pop\n");
