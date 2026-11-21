/* ARCADE MODE > CONFIG: a RANK GAUGE ON/OFF row (row 6, after CONTINUE), in the launcher and in KURO.
 *
 * The gauge itself (research/phase17): Arrange's RANK gauge routine 0x00129360 draws only in Arrange or Arcade
 * PRACTICE; "ON" lets it draw in every Arcade game and blanks the empty side's "PRESS START / button" text it
 * would sit on. Those are 5 code words (scripts/build_ee_hooks.py RANK_GAUGE_EDITS); opt_set() rewrites them and
 * flushes the caches, so the option takes effect at once. The executable starts with the ON words baked in.
 *
 * The menu (retail CONFIG, frontend state at 0x001CBxxx-0x001CC5xx, cursor row $gp-26732): its label table
 * 0x002A9220 gets the new row 6 (FIGHTER TYPE, KEY CONFIG, EXIT move to 7-9 in the table's spare slots), the row
 * count goes 9 -> 10 (draw loop, cursor wrap), the accept dispatcher's row numbers 6/7/8 -> 7/8/9, and its
 * "no handler" exit for row 6 goes to cfg_accept_entry (toggle). The value column comes from cfg_value(), called
 * where the retail loop looked up CONTINUE's value; the help text from cfg_desc (the retail table has no room).
 * Leaf code: temporaries only (built with the s-registers fixed; tests/test_ee_hooks.py checks the listing).
 */
#include "ibara_ps2.h"

#pragma GCC optimize("Os")

#define GAME_SOUND     ((void (*)(int, int))0x001370E0u) /* (95, 36): the menus' accept sound */
#define ON_OFF_NAMES   0x00338930u                         /* $gp-29632: "OFF", "ON" (CONTINUE's values) */

u32 opt_gauge = 1u; /* RANK GAUGE: 1 ON (the baked state), 0 OFF (retail) */

static const u32 g_addr[5] = {0x00129394u, 0x0012C7C0u, 0x0012C7E4u, 0x0012CA00u, 0x0012CA24u};
static const u32 g_word[2][5] = {
	{0x106000F0u, 0x24845F20u, 0x24845F30u, 0x24845F20u, 0x24845F30u}, /* OFF: retail */
	{0x00000000u, 0x24845F40u, 0x24845F40u, 0x24845F40u, 0x24845F40u}, /* ON: draw, blank PRESS START */
};

const char rank_label[] = "RANK GAUGE"; /* label-table word 0x002A9238 */
/* Help text, Shift-JIS: "ランクゲージの表示を" / (retail) "設定できます。" */
static const char rank_help[] = "\x83\x89\x83\x93\x83\x4e\x83\x51\x81\x5b\x83\x57\x82\xcc\x95\x5c\x8e\xa6\x82\xf0";

/* Two help lines per row (retail 0x002A9310 holds 9 rows, with the next table right after it). */
const char *const cfg_desc[20] = {
	(const char *)0x003022E0u, (const char *)0x00302300u, /* DIFFICULTY 1 */
	(const char *)0x00302310u, (const char *)0x00302300u, /* DIFFICULTY 2 */
	(const char *)0x00302330u, (const char *)0x00302300u, /* PLAYER STOCK */
	(const char *)0x00302350u, (const char *)0x00302370u, /* BOMB STOCK */
	(const char *)0x00302390u, (const char *)0x003023B0u, /* EXTEND */
	(const char *)0x003023C0u, (const char *)0x00301FD8u, /* CONTINUE */
	rank_help, (const char *)0x00302300u,                 /* RANK GAUGE */
	(const char *)0x003023E0u, (const char *)0x00302400u, /* FIGHTER TYPE */
	(const char *)0x00302420u, (const char *)0x00302400u, /* KEY CONFIG */
	(const char *)0x00301EF0u, (const char *)0x00301F10u, /* EXIT */
};

void opt_set(u32 on)
{
	unsigned i;
	opt_gauge = on;
	for (i = 0; i < 5u; i++)
		EE_RAM(u32, g_addr[i]) = g_word[on][i];
	__asm__ __volatile__( /* FlushCache(0) write back data, FlushCache(2) invalidate instructions */
		"move $4, $0\n\tli $3, 100\n\tsyscall\n"
		"li $4, 2\n\tli $3, 100\n\tsyscall\n"
		: : : "v0", "v1", "a0", "a1", "a2", "a3", "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "t9",
		      "memory");
}

/* Value text of a CONFIG row: replaces the retail CONTINUE lookup at 0x001CBF70 (row, CONTINUE's setting, value
 * chosen so far for the row) and returns the value to draw (0 = none). */
const char *cfg_value(u32 row, u32 cont, const char *cur)
{
	const char *const *names = (const char *const *)ON_OFF_NAMES;
	if (row == 5u)
		return names[cont];
	if (row == 6u)
		return names[opt_gauge & 1u];
	return cur;
}

void cfg_toggle(void)
{
	opt_set(opt_gauge ^ 1u);
	GAME_SOUND(95, 36);
}

/* Reached from the accept dispatcher for a row without a retail handler (v1 = cursor row). */
__asm__(
	".set push\n.set noreorder\n"
	".globl cfg_accept_entry\n"
	".type cfg_accept_entry, @function\n"
	"cfg_accept_entry:\n"
	"	li	$2, 6\n"
	"	bne	$3, $2, 1f\n"
	"	nop\n"
	"	jal	cfg_toggle\n"
	"	nop\n"
	"1:	j	0x001CBE20\n"
	"	nop\n"
	".size cfg_accept_entry, . - cfg_accept_entry\n"
	".set pop\n");

/* ARRANGE MODE gets a PRACTICE row (row 1, as in ARCADE MODE): GAME START, PRACTICE, CONFIG, EXIT.
 * It opens the retail practice menu (state 4, the one ARCADE MODE uses) with prac_arrange set. The retail practice
 * start (0x001CB3C0) sets the PRACTICE flag and clears the Arrange flag ($gp-28076) at 0x001CB3E0; that store
 * becomes `jal prac_start`, which stores prac_arrange instead. With both flags set the game runs Arrange from the
 * chosen stage (Arrange HUD, formations, sub-weapons; Game Over returns to the practice menu; research/phase17).
 * Leaving the practice menu (EXIT or cancel) returns to the menu it came from, on its PRACTICE row (prac_exit_state),
 * and clears prac_arrange; ARCADE MODE's own practice therefore always runs Arcade (in KURO: KURO). */
u32 prac_arrange; /* 1 while the practice menu was opened from ARRANGE MODE */

#define FRONT_STATE  0x00338F58u /* $gp-28056: frontend state (2 ARCADE MODE, 4 PRACTICE, 9 ARRANGE MODE) */
#define FRONT_ROW    0x0033948Cu /* $gp-26724: cursor row on entering a state */
#define FRONT_EDIT   0x00338F5Cu /* $gp-28052: row being edited (-1 none) */
#define FRONT_ANIM   0x00338F64u /* $gp-28044: state transition counter */

/* Help text for ARRANGE MODE's 4 rows (retail 0x002A93F0 holds 3 rows, with the next table right after it). */
const char *const arr_desc[8] = {
	(const char *)0x00302630u, (const char *)0x00301D70u, /* GAME START */
	(const char *)0x00301FA0u, (const char *)0x00301D70u, /* PRACTICE: retail "練習モードでゲームを / 開始します。" */
	(const char *)0x00302650u, (const char *)0x00301DE0u, /* CONFIG */
	(const char *)0x00301E00u, (const char *)0x00301E20u, /* EXIT */
};

void arr_practice(void)
{
	prac_arrange = 1u;
	EE_RAM(u32, FRONT_STATE) = 4u; /* as ARCADE MODE's PRACTICE handler (0x001CAB0C) */
	EE_RAM(u32, FRONT_ROW) = 0u;
	EE_RAM(s32, FRONT_EDIT) = -1;
	EE_RAM(u32, FRONT_ANIM) = 0u;
	GAME_SOUND(95, 36);
}

__asm__(
	".set push\n.set noreorder\n.set noat\n"
	/* replaces `sw zero, -28076(gp)` in the practice start; only $at is used (v0-a3 are live there) */
	".globl prac_start\n"
	".type prac_start, @function\n"
	"prac_start:\n"
	"	lui	$1, %hi(prac_arrange)\n"
	"	lw	$1, %lo(prac_arrange)($1)\n"
	"	jr	$31\n"
	"	sw	$1, -28076($28)\n"
	".size prac_start, . - prac_start\n"
	/* replaces `li v0, 2` (state ARCADE MODE) on both ways out of the practice menu: v0 = 9 (ARRANGE MODE) when it
	 * was opened from there, else 2; clears the flag. Only v0 and $at are used. */
	".globl prac_exit_state\n"
	".type prac_exit_state, @function\n"
	"prac_exit_state:\n"
	"	lui	$1, %hi(prac_arrange)\n"
	"	lw	$2, %lo(prac_arrange)($1)\n"
	"	sw	$0, %lo(prac_arrange)($1)\n"
	"	beqz	$2, 1f\n"
	"	li	$2, 2\n"
	"	li	$2, 9\n"
	"1:	jr	$31\n"
	"	nop\n"
	".size prac_exit_state, . - prac_exit_state\n"
	/* reached from ARRANGE MODE's accept dispatcher for a row without a retail handler (v1 = cursor row) */
	".globl arr_accept_entry\n"
	".type arr_accept_entry, @function\n"
	"arr_accept_entry:\n"
	"	li	$2, 1\n"
	"	bne	$3, $2, 1f\n"
	"	nop\n"
	"	jal	arr_practice\n"
	"	nop\n"
	"1:	j	0x001CCAE4\n"
	"	nop\n"
	".size arr_accept_entry, . - arr_accept_entry\n"
	/* replaces `lw v1, -28056(gp)` in the menu header selector 0x001C9570 (states 2-8 ARCADE MODE, 9-12 ARRANGE
	 * MODE): reports the practice menu (4) as 9 while it belongs to ARRANGE MODE. Only v1 and $at are used. */
	".globl hdr_state\n"
	".type hdr_state, @function\n"
	"hdr_state:\n"
	"	lw	$3, -28056($28)\n"
	"	li	$1, 4\n"
	"	bne	$3, $1, 1f\n"
	"	lui	$1, %hi(prac_arrange)\n"
	"	lw	$1, %lo(prac_arrange)($1)\n"
	"	beqz	$1, 1f\n"
	"	nop\n"
	"	li	$3, 9\n"
	"1:	jr	$31\n"
	"	nop\n"
	".size hdr_state, . - hdr_state\n"
	".set pop\n");
