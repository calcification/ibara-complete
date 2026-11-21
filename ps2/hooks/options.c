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

/* ARCADE MODE > PRACTICE: a GAME MODE row (row 4, before EXIT): ARCADE or ARRANGE (in KURO: KURO or ARRANGE).
 * The retail practice start (0x001CB3C0) sets the PRACTICE flag and clears the Arrange flag ($gp-28076) at
 * 0x001CB3E0; that store becomes `jal prac_start`, which stores prac_arrange instead. With both flags set the game
 * runs Arrange from the chosen stage (Arrange HUD, formations, sub-weapons; Game Over returns to PRACTICE), the same
 * way Arcade practice works (research/phase17). Arcade's GAME START clears the flag again (0x001CAD04). */
u32 prac_arrange; /* 0 ARCADE (or KURO), 1 ARRANGE */
__attribute__((weak)) const char prac_name0[] = "ARCADE"; /* bl_return.c: "KURO" */
static const char prac_name1[] = "ARRANGE";
const char prac_label[] = "GAME MODE"; /* label-table word 0x002A9040 */
/* Help line 1, Shift-JIS "練習するゲームモードを" (line 2: retail "選択できます。") */
const char prac_help[] = "\x97\xfb\x8f\x4b\x82\xb7\x82\xe9\x83\x51\x81\x5b\x83\x80\x83\x82\x81\x5b\x83\x68\x82\xf0";

/* Value text of a PRACTICE row: replaces the PLAY DATA LIST lookup at 0x001CB058 (row, value so far, play-data
 * index -1..4). */
const char *prac_value(u32 row, const char *cur, s32 data)
{
	if (row == 3u)
		return ((const char *const *)0x002A9150u)[data + 1]; /* DEFAULT, DATA 1..5 */
	if (row == 4u)
		return prac_arrange ? prac_name1 : prac_name0;
	return cur;
}

void prac_toggle(void)
{
	prac_arrange ^= 1u;
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
	/* reached from the PRACTICE accept dispatcher for a row without a retail handler (v1 = cursor row) */
	".globl prac_accept_entry\n"
	".type prac_accept_entry, @function\n"
	"prac_accept_entry:\n"
	"	li	$2, 4\n"
	"	bne	$3, $2, 1f\n"
	"	nop\n"
	"	jal	prac_toggle\n"
	"	nop\n"
	"1:	j	0x001CAF40\n"
	"	nop\n"
	".size prac_accept_entry, . - prac_accept_entry\n"
	".set pop\n");
