/* Instant KURO: Black Label as a mode of the main executable, switched on and off without reloading the game.
 *
 * The frontend executable carries this project's whole hook image (video.c and options.c for every mode, plus
 * the Black Label code: xtc.c, xtc_hud.c, bl_enemy.c, bl_player.c). The Black Label code words — call sites of
 * its hooks, rule patches, the enemy part-HP tables — are not baked in: the builder appends them as a table of
 * (address, retail word, Black Label word) after the image (scripts/build_ee_hooks.py, kuro_tab/kuro_tab_n) and
 * kuro_set() writes one column or the other, then flushes the caches. A word is only written when it still holds
 * the other column's value, so data the game rewrote is left alone.
 *
 *   Mode Select row KURO (dispatcher 0x001D42A0, at 0x001D42AC) -> kuro_enter_entry: Black Label on, then ARCADE MODE's menu
 *     (state 2: GAME START, PRACTICE, CONFIG, EXIT) as the Arcade row would open it.
 *   Leaving that menu (EXIT row 0x001CAAC4, cancel 0x001CA958) -> kuro_leave_entry: Black Label off, and Mode
 *     Select comes back on the KURO row instead of ARCADE.
 *   Any frame with the frontend at the title or Mode Select (state <= 1; a game keeps its submenu's state, 3 or 4),
 *     or the attract sequence starting after a Game Over -> off (kuro_frame).
 * Leaf code: temporaries only (the per-frame stub saves no s-registers).
 */
#include "ibara_ps2.h"

#pragma GCC optimize("Os")

#define GAME_SOUND  ((void (*)(int, int))0x001370E0u)
#define FRONT_STATE 0x00338F58u /* $gp-28056 */
#define FRONT_ROW   0x0033948Cu /* $gp-26724: cursor row on entering a state */
#define FRONT_ANIM  0x00338F64u /* $gp-28044 */

struct kuro_word { u32 addr, retail, kuro; };

/* Filled in by the builder (the table follows the image). */
const struct kuro_word *volatile kuro_tab = 0;
volatile u32 kuro_tab_n = 0u;
volatile u32 kuro_row = 2u;      /* Mode Select row of KURO (builder: 2 or 5) */
volatile u32 video_enabled = 1u; /* 0 when the build's video profile has no runtime part */

u32 kuro_on;

void video_frame(void);
void xtc_reset(void);

static void kuro_set(u32 on)
{
	const struct kuro_word *w = kuro_tab;
	u32 i, n = kuro_tab_n;
	for (i = 0; i < n; i++, w++) {
		volatile u32 *p = (volatile u32 *)w->addr;
		const u32 from = on ? w->retail : w->kuro, to = on ? w->kuro : w->retail;
		if (*p == from)
			*p = to;
	}
	kuro_on = on;
	__asm__ __volatile__( /* FlushCache(0) write back data, FlushCache(2) invalidate instructions */
		"move $4, $0\n\tli $3, 100\n\tsyscall\n"
		"li $4, 2\n\tli $3, 100\n\tsyscall\n"
		: : : "v0", "v1", "a0", "a1", "a2", "a3", "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "t9",
		      "memory");
}

void kuro_enter(void)
{
	xtc_reset();
	kuro_set(1u);
	EE_RAM(u32, FRONT_STATE) = 2u; /* as the Arcade row (0x001CA800) */
	EE_RAM(u32, FRONT_ROW) = 0u;
	EE_RAM(u32, FRONT_ANIM) = 0u;
	GAME_SOUND(95, 36);
}

/* Mode Select row to return to from ARCADE MODE's menu. */
u32 kuro_leave(void)
{
	if (!kuro_on)
		return 0u;
	kuro_set(0u);
	return kuro_row;
}

/* Per frame, after video_frame: KURO off at the title / Mode Select, or when the attract sequence starts after a
 * Game Over (the game keeps the submenu's state then; its attract flag $gp-28276 goes 0 -> 1, set with the demo's
 * Arcade rules at 0x0013DDBC, cleared by a game start at 0x0013DB10). The edge, not the level, so a flag left at 1
 * from an earlier attract cycle cannot switch KURO off in its own menus. */
#define ATTRACT 0x00338E7Cu /* u8 */
static u8 attract_last;

void kuro_frame(void)
{
	const u8 attract = EE_RAM(u8, ATTRACT);
	if (kuro_on && (EE_RAM(u32, FRONT_STATE) <= 1u || (attract && !attract_last)))
		kuro_set(0u);
	attract_last = attract;
}

__asm__(
	".set push\n.set noreorder\n"
	/* Per frame (main-loop display call, every screen): video_frame (when the build has the runtime video switch),
	 * then kuro_frame. Assembly so the stack stays 16-byte aligned as the stub left it (a C frame here was 24 bytes,
	 * and the game then hung at its first NOW LOADING). */
	".globl frame_hook\n"
	".type frame_hook, @function\n"
	"frame_hook:\n"
	"	addiu	$29, $29, -16\n"
	"	sw	$31, 0($29)\n"
	"	lui	$8, %hi(video_enabled)\n"
	"	lw	$8, %lo(video_enabled)($8)\n"
	"	beqz	$8, 1f\n"
	"	nop\n"
	"	jal	video_frame\n"
	"	nop\n"
	"1:	jal	kuro_frame\n"
	"	nop\n"
	"	lw	$31, 0($29)\n"
	"	jr	$31\n"
	"	addiu	$29, $29, 16\n"
	".size frame_hook, . - frame_hook\n"
	/* replaces the KURO row's LoadExecPS2 in the Mode Select dispatcher (0x001D42AC; v1 = cursor row, already
	 * known to be KURO's): enter, then resume the menu drawing as the dispatcher did after its syscall */
	".globl kuro_enter_entry\n"
	".type kuro_enter_entry, @function\n"
	"kuro_enter_entry:\n"
	"	jal	kuro_enter\n"
	"	nop\n"
	"	j	0x001CA5AC\n"
	"	nop\n"
	".size kuro_enter_entry, . - kuro_enter_entry\n"
	/* replaces `li v0, 1` (state Mode Select) on ARCADE MODE's two ways out; its delay slot loaded a0 = 76 (the sound
	 * argument), kept here. Returns v0 = 1 and v1 = the Mode Select row, which the patched `sw v1, -26724(gp)`
	 * stores instead of 0. */
	".globl kuro_leave_entry\n"
	".type kuro_leave_entry, @function\n"
	"kuro_leave_entry:\n"
	"	addiu	$29, $29, -16\n"
	"	sw	$31, 0($29)\n"
	"	jal	kuro_leave\n"
	"	sw	$4, 4($29)\n"
	"	move	$3, $2\n"
	"	lw	$4, 4($29)\n"
	"	lw	$31, 0($29)\n"
	"	addiu	$29, $29, 16\n"
	"	jr	$31\n"
	"	li	$2, 1\n"
	".size kuro_leave_entry, . - kuro_leave_entry\n"
	".set pop\n");
