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

#define GAME_SOUND(a, b) GAME_CALL2(0x001370E0u, a, b) /* (95, 36): the menus' accept sound */
#define ON_OFF_NAMES   0x00338930u                         /* $gp-29632: "OFF", "ON" (CONTINUE's values) */

u32 opt_gauge = 1u; /* RANK GAUGE: 1 ON (the baked state), 0 OFF (retail) */

static const u32 g_addr[5] = {0x00129394u, 0x0012C7C0u, 0x0012C7E4u, 0x0012CA00u, 0x0012CA24u};
static const u32 g_word[2][5] = {
	{0x106000F0u, 0x24845F20u, 0x24845F30u, 0x24845F20u, 0x24845F30u}, /* OFF: retail */
	{0x00000000u, 0x24845F40u, 0x24845F40u, 0x24845F40u, 0x24845F40u}, /* ON: draw, blank PRESS START */
};

const char rank_label[] = "RANK GAUGE"; /* label-table word 0x002A9238 */
/* Help text, Shift-JIS: "ランクゲージの表示を" / (retail) "設定できます。" */
#ifdef ARCADE_SLOWDOWN_CONFIG
const char slowdown_label[] = "SLOWDOWN";
const char slowdown_help[] = "\x83\x58\x83\x8d\x81\x5b\x83\x5f\x83\x45\x83\x93\x82\xf0"; /* スローダウンを */
extern const char noir_return_help[];
extern u32 kuro_on;
void arcade_slowdown_apply(u32 active);
u32 cfg_rank_enabled = 1u;
u32 opt_slowdown;
#endif

static const char rank_help[] = "\x83\x89\x83\x93\x83\x4e\x83\x51\x81\x5b\x83\x57\x82\xcc\x95\x5c\x8e\xa6\x82\xf0";

/* Two help lines per row (retail 0x002A9310 holds 9 rows, with the next table right after it). */
#ifdef KURO_PRESENTATION
#ifdef ARCADE_SLOWDOWN_CONFIG
const char *cfg_desc[22] = {
#else
const char *cfg_desc[20] = {
#endif
#else
const char *const cfg_desc[20] = {
#endif
	(const char *)0x003022E0u, (const char *)0x00302300u, /* DIFFICULTY 1 */
	(const char *)0x00302310u, (const char *)0x00302300u, /* DIFFICULTY 2 */
	(const char *)0x00302330u, (const char *)0x00302300u, /* PLAYER STOCK */
	(const char *)0x00302350u, (const char *)0x00302370u, /* BOMB STOCK */
	(const char *)0x00302390u, (const char *)0x003023B0u, /* EXTEND */
	(const char *)0x003023C0u, (const char *)0x00301FD8u, /* CONTINUE */
	rank_help, (const char *)0x00302300u,                 /* RANK GAUGE */
	(const char *)0x003023E0u, (const char *)0x00302400u, /* FIGHTER TYPE */
	(const char *)0x00302420u, (const char *)0x00302400u, /* KEY CONFIG */
#ifdef ARCADE_SLOWDOWN_CONFIG
	slowdown_help, (const char *)0x00302300u,              /* SLOWDOWN */
#endif
	(const char *)0x00301EF0u, (const char *)0x00301F10u, /* EXIT */
};

static void flush_option_edits(void)
{
	__asm__ __volatile__( /* FlushCache(0) write back data, FlushCache(2) invalidate instructions */
		"move $4, $0\n\tli $3, 100\n\tsyscall\n"
		"li $4, 2\n\tli $3, 100\n\tsyscall\n"
		: : : "v0", "v1", "a0", "a1", "a2", "a3", "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "t9",
		      "memory");
}

void opt_set(u32 on)
{
	opt_gauge = on;
	for (unsigned i = 0; i < 5u; i++)
		EE_RAM(u32, g_addr[i]) = g_word[on][i];
	flush_option_edits();
}

#ifdef ARCADE_SLOWDOWN_CONFIG
/* Arcade and Noir share the retail CONFIG routine. Noir uses the shorter
 * list with EXIT in Arcade's SLOWDOWN slot. kuro_set flushes these edits.
 */
void cfg_set_noir(u32 noir)
{
	const u32 fighter = 6u + cfg_rank_enabled;
	const u32 slowdown = fighter + 2u;
	const u32 exit = slowdown + !noir;
	EE_RAM(u32, 0x002A9220u + slowdown * 4u) = noir ? 0x00301C50u : (u32)slowdown_label;
	EE_RAM(u32, 0x001CBFE4u) = 0x2A420000u | (exit + 1u);
	EE_RAM(u32, 0x001CC170u) = 0x28410000u | (exit + 1u);
	EE_RAM(u32, 0x001CC1FCu) = 0x24020000u | exit;
	EE_RAM(u32, 0x001CC290u) = 0x24020000u | exit;
	cfg_desc[fighter * 2u] = (const char *)(noir ? 0x003023F2u : 0x003023E0u);
	cfg_desc[(fighter + 1u) * 2u] = (const char *)(noir ? 0x00302432u : 0x00302420u);
	cfg_desc[slowdown * 2u] = noir ? noir_return_help : slowdown_help;
	cfg_desc[slowdown * 2u + 1u] = (const char *)(noir ? 0x00301F10u : 0x00302300u);
	arcade_slowdown_apply(!noir && opt_slowdown);
}
#endif

/* Value text of a CONFIG row: replaces the retail CONTINUE lookup at 0x001CBF70 (row, CONTINUE's setting, value
 * chosen so far for the row) and returns the value to draw (0 = none). */
const char *cfg_value(u32 row, u32 cont, const char *cur)
{
	const char *const *names = (const char *const *)ON_OFF_NAMES;
	if (row == 5u)
		return names[cont];
#ifdef ARCADE_SLOWDOWN_CONFIG
	if (!kuro_on && row == 8u + cfg_rank_enabled)
		return names[opt_slowdown];
	if (cfg_rank_enabled && row == 6u)
#else
	if (row == 6u)
#endif
		return names[opt_gauge & 1u];
	return cur;
}

void cfg_toggle(void)
{
	opt_set(opt_gauge ^ 1u);
	GAME_SOUND(95, 36);
}

#ifdef ARCADE_SLOWDOWN_CONFIG
void cfg_toggle_row(u32 row)
{
	if (cfg_rank_enabled && row == 6u) {
		cfg_toggle();
	} else if (!kuro_on && row == 8u + cfg_rank_enabled) {
		opt_slowdown ^= 1u;
		arcade_slowdown_apply(opt_slowdown);
		flush_option_edits();
		GAME_SOUND(95, 36);
	}
}
#endif

/* Reached from the accept dispatcher for a row without a retail handler (v1 = cursor row). */
__asm__(
	".set push\n.set noreorder\n"
	".globl cfg_accept_entry\n"
	".type cfg_accept_entry, @function\n"
	"cfg_accept_entry:\n"
#ifdef ARCADE_SLOWDOWN_CONFIG
	"	jal	cfg_toggle_row\n"
	"	move	$4, $3\n"
#else
	"	li	$2, 6\n"
	"	bne	$3, $2, 1f\n"
	"	nop\n"
	"	jal	cfg_toggle\n"
	"	nop\n"
	"1:\n"
#endif
	"	j	0x001CBE20\n"
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

/* ARRANGE CONFIG gets Arcade's PLAYER STOCK, BOMB STOCK, EXTEND and CONTINUE rows, with Arrange's own values (no
 * DIFFICULTY rows: Arrange has its own rank). Rows: FIGHTER TYPE, BULLET DESIGN, PLAYER STOCK, BOMB STOCK, EXTEND,
 * CONTINUE, KEY CONFIG, EXIT. A Circle press on a new row cycles its value. The defaults play as retail Arrange,
 * and the values last for the session (like RANK GAUGE; not saved).
 *
 * Retail Arrange's rules (research/phase26):
 *   PLAYER STOCK  fixed 2 (0x0012D8E4 `li a0,2` in the player set-up 0x0012D840)
 *   BOMB STOCK    one full bomb (+40 fragments; 0x0012D5D4 sends Arrange to 0x0012D7CC) unless Arcade's BOMB STOCK
 *                 is 0 (0x0012D5BC)
 *   EXTEND        first at 10,000,000 (0x0012D8C0 -> 0x0012D930), then every 10,000,000 (0x0013ABD8 -> 0x0013AC54)
 *   CONTINUE      none: the three continue checks (0x0012C5B4, 0x0012C734, 0x0012C934) take the CONTINUE OFF path
 * arr_rules_apply() rewrites those words for Arrange games and restores the retail words for the others. It runs
 * at the start of the player set-up (0x0012D840, every game start and every join), only rewriting and flushing
 * when the wanted words change. */
#define ARCADE_FLAG   0x00338F44u /* $gp-28076: 1 Arrange */
#define EXT_FIRST     0x00338E68u /* $gp-28296: first extend score */
#define EXT_EVERY     0x00338E6Cu /* $gp-28292: later extends every (1e9 = none) */

u8 arr_stock = 2u;  /* PLAYER STOCK value index (0x002A9290: "1".."6"); retail Arrange 2 */
u8 arr_bomb = 2u;   /* BOMB STOCK value index (0x002A92B0: "0","1/2","1","2","3","4"); retail Arrange "1" */
u8 arr_extend;      /* 0 10M EVERY (retail Arrange), 1-7 Arcade's EXTEND values 0-6 */
u8 arr_continue;    /* 0 OFF (retail), 1 ON */

static const char *const arr_extend_names[8] = {
	"10M EVERY", "NOT EXTEND", "1M EVERY", "2M EVERY", "3M EVERY", "2M ONLY", "4M ONLY", "6M ONLY",
}; /* one line of at most 12 characters (the value column ends at the screen edge) */

const char *const arrcfg_label[8] = {
	(const char *)0x00301CC0u, (const char *)0x00301CD0u, /* FIGHTER TYPE, BULLET DESIGN */
	(const char *)0x00302110u, (const char *)0x00302120u, /* PLAYER STOCK, BOMB STOCK */
	(const char *)0x00302130u, (const char *)0x00302138u, /* EXTEND, CONTINUE */
	(const char *)0x00301CE0u, (const char *)0x00301C50u, /* KEY CONFIG, EXIT */
};

/* Two help lines per row: Arrange's own for its retail rows, Arcade CONFIG's for the new ones. */
const char *const arrcfg_desc[16] = {
	(const char *)0x00302690u, (const char *)0x00302300u, /* FIGHTER TYPE */
	(const char *)0x003026B0u, (const char *)0x003026C8u, /* BULLET DESIGN */
	(const char *)0x00302330u, (const char *)0x00302300u, /* PLAYER STOCK */
	(const char *)0x00302350u, (const char *)0x00302370u, /* BOMB STOCK */
	(const char *)0x00302390u, (const char *)0x003023B0u, /* EXTEND */
	(const char *)0x003023C0u, (const char *)0x00301FD8u, /* CONTINUE */
	(const char *)0x003026E0u, (const char *)0x00302300u, /* KEY CONFIG */
	(const char *)0x00302700u, (const char *)0x00301F10u, /* EXIT */
};

/* Value text of an ARRANGE CONFIG row (0 = none); replaces the retail BULLET DESIGN lookup at 0x001CCE64. */
const char *arrcfg_value(u32 row)
{
	switch (row) {
	case 1u: return (const char *)EE_RAM(u32, 0x002A9408u + EE_RAM(u32, 0x00338FACu) * 4u); /* $gp-27972 */
	case 2u: return (const char *)EE_RAM(u32, 0x002A9290u + arr_stock * 4u);
	case 3u: return (const char *)EE_RAM(u32, 0x002A92B0u + arr_bomb * 4u);
	case 4u: return arr_extend_names[arr_extend];
	case 5u: return ((const char *const *)ON_OFF_NAMES)[arr_continue];
	}
	return 0;
}

void arrcfg_cycle(u32 row)
{
	if (row == 2u)
		arr_stock = arr_stock < 5u ? arr_stock + 1u : 0u;
	else if (row == 3u)
		arr_bomb = arr_bomb < 5u ? arr_bomb + 1u : 0u;
	else if (row == 4u)
		arr_extend = (arr_extend + 1u) & 7u;
	else if (row == 5u)
		arr_continue ^= 1u;
	else
		return;
	GAME_SOUND(95, 36);
}

/* (address, retail word); the Arrange words are built in arr_rules_apply */
static const u32 rule_addr[12] = {
	0x0012D8E4u,                                     /* li a0,2 (Arrange's stock) */
	0x0012D5A0u, 0x0012D5D4u, 0x0012D7D8u, 0x0012D7FCu, /* bomb stock */
	0x0012D8C0u, 0x0013ABD8u,                        /* Arrange's fixed first extend and interval */
	0x0012C594u, 0x0012C5B4u, 0x0012C714u, 0x0012C734u, 0x0012C924u, /* continue */
};
static const u32 rule_retail[12] = {
	0x24040002u,
	0x93858F14u, 0x1460007Du, 0x10600008u, 0x93858F14u,
	0x1460001Bu, 0x14600019u,
	0x93838EFCu, 0x14800046u, 0x93878EFCu, 0x14C0009Bu, 0x93838EFCu,
};
#define RULE_CONT2 0x0012C934u /* bnez v1 (Arrange) after the game-over continue check */
static u32 rules_key = 0xFFFFFFFFu; /* words currently in place (0 = retail) */

void arr_rules_apply(void)
{
	const u32 arrange = EE_RAM(u32, ARCADE_FLAG) != 0u;
	const u32 key = arrange ? 0x80000000u | arr_stock | (u32)arr_bomb << 4 | (u32)arr_extend << 8 |
	                          (u32)arr_continue << 12 : 0u;
	u32 w[12];
	if (key == rules_key)
		return;
	for (unsigned i = 0; i < 12u; i++)
		w[i] = rule_retail[i];
	u32 cont2 = 0x14600089u;
	if (arrange) {
		w[0] = 0x24040000u | arr_stock;
		w[1] = w[4] = 0x24050000u | arr_bomb; /* li a1, value */
		w[2] = 0u;                            /* half bomb (setting 1) as in Arcade */
		w[3] = 0x10000008u;                   /* always add (setting - 2) bombs, as in Arcade */
		if (arr_extend) {
			w[5] = w[6] = 0u; /* first extend from $gp-28296, later ones every $gp-28292, as in Arcade */
			const u32 i = arr_extend - 1u;
			EE_RAM(u32, EXT_FIRST) = EE_RAM(u32, 0x00213540u + i * 4u);
			EE_RAM(u32, EXT_EVERY) = EE_RAM(u32, 0x00213560u + i * 4u) ? EE_RAM(u32, EXT_FIRST) : 1000000000u;
		}
		if (arr_continue) {
			w[7] = 0x24030001u; /* li v1,1 */
			w[8] = 0u;
			w[9] = 0x24070001u; /* li a3,1 */
			w[10] = 0u;
			w[11] = 0x24030001u;
			cont2 = 0u;
		}
	}
	if ((rules_key & 0x80000000u) && (rules_key >> 8 & 15u) && !(arrange && arr_extend))
		GAME_CALL2(0x0013E290u, 0, 0); /* back to Arcade's EXTEND values */
	for (unsigned i = 0; i < 12u; i++)
		EE_RAM(u32, rule_addr[i]) = w[i];
	EE_RAM(u32, RULE_CONT2) = cont2;
	rules_key = key;
	flush_option_edits();
}

__asm__(
	".set push\n.set noreorder\n"
	/* reached from the accept dispatcher for a row without a retail handler (v1 = cursor row) */
	".globl arrcfg_accept_entry\n"
	".type arrcfg_accept_entry, @function\n"
	"arrcfg_accept_entry:\n"
	"	jal	arrcfg_cycle\n"
	"	move	$4, $3\n"
	"	j	0x001CCDB0\n"
	"	nop\n"
	".size arrcfg_accept_entry, . - arrcfg_accept_entry\n"
	/* replaces the player set-up's first word `addiu sp,sp,-32` (0x0012D840; a0 = side) */
	".globl arr_rules_entry\n"
	".type arr_rules_entry, @function\n"
	"arr_rules_entry:\n"
	"	addiu	$29, $29, -16\n"
	"	sd	$31, 0($29)\n"
	"	jal	arr_rules_apply\n"
	"	sd	$4, 8($29)\n"
	"	ld	$31, 0($29)\n"
	"	ld	$4, 8($29)\n"
	"	addiu	$29, $29, -16\n" /* our -16 and this -16: the displaced `addiu sp,sp,-32` */
	"	j	0x0012D844\n"
	"	nop\n"
	".size arr_rules_entry, . - arr_rules_entry\n"
	".set pop\n");
