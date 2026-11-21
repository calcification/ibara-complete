/* Black Label ship kind (straight / spread) and bombs, KURO only (switched with the KURO table; research/phase18).
 *
 * BL lets each player pick straight or spread and type A-D, and indexes the arcade mechanics by kind * 4 + type
 * (Phase 13: BL straight A-D = arcade/PS2 Bond A-D, spread A-D = Dyne A-D: shots, speeds, bombs). PS2 Arcade has
 * no ship select: CONFIG > FIGHTER TYPE sets the type per player (config 0x004E5050 / 0x004E5054) and the pilot
 * is the side, so the player-start code (0x001CE728) makes the ship word side * 4 + type. In KURO the FIGHTER TYPE
 * rows take 8 values, and the ship word is side * 4 XOR value: values 4-7 give the other pilot's set (P1: spread,
 * P2: straight). Retail values 0-3 give the retail ship. kuro.c keeps the choice while KURO is off and clamps the
 * config to 0-3 for the retail modes.
 *
 * Bombs: BL's per-ship bomb routines are the arcade's with relocated operands, except type D (0C079600, shared by
 * both kinds), which picks its pattern table and repeat count by ship kind where the arcade (0C068570) and PS2
 * (0x0011B460) use the player side: bomb_d_kind gives PS2 the kind (t9 = table, t1 = repeat count). BL's bomb
 * trigger (0C073600) also drops the arcade's harder(0x1000) per bomb, as PS2's Arrange does (patches in
 * scripts/build_ee_hooks.py BL_SHIP_PATCHES). Assembly only: called from the middle of retail routines.
 */
#include "ibara_ps2.h"

static const char s_a[] = "STRAIGHT A", s_b[] = "STRAIGHT B", s_c[] = "STRAIGHT C", s_d[] = "STRAIGHT D";
static const char p_a[] = "SPREAD A", p_b[] = "SPREAD B", p_c[] = "SPREAD C", p_d[] = "SPREAD D";
const char *const ship_tab_p1[8] = {s_a, s_b, s_c, s_d, p_a, p_b, p_c, p_d}; /* P1: 0-3 straight (Bond) */
const char *const ship_tab_p2[8] = {p_a, p_b, p_c, p_d, s_a, s_b, s_c, s_d}; /* P2: 0-3 spread (Dyne) */

/* Help lines, read as [row * 8 + value * 2] (+1): the retail table 0x002A9380 is Bond A-D then Dyne A-D (two lines
 * each), so row 0 values 4-7 already land on Dyne; a copy of Bond's after it serves row 1 values 4-7. */
#define H(a, b) (const char *)(a), (const char *)(b)
const char *const ship_help[24] = {
	H(0x00302480u, 0x003024A0u), H(0x003024C0u, 0x003024E0u), H(0x00302500u, 0x00302520u), H(0x00302530u, 0x00302550u),
	H(0x00302570u, 0x003024A0u), H(0x00302570u, 0x00302590u), H(0x003025B0u, 0x003025D0u), H(0x003025B0u, 0x00302550u),
	H(0x00302480u, 0x003024A0u), H(0x003024C0u, 0x003024E0u), H(0x00302500u, 0x00302520u), H(0x00302530u, 0x00302550u),
};

__asm__(
	".set push\n.set noreorder\n.set noat\n"
	/* FIGHTER TYPE edit popup, replaces `lui s3,0x2b` (0x001C970C; `addiu s3` after it is a nop in KURO): s3 = the
	 * label table of the row being edited ($gp-28052: 0 PLAYER 1, 1 PLAYER 2). Uses only $at and s3. */
	".globl ship_popup_tab\n"
	".type ship_popup_tab, @function\n"
	"ship_popup_tab:\n"
	"	lw	$1, -28052($28)\n"
	"	lui	$19, %hi(ship_tab_p1)\n"
	"	bnez	$1, 1f\n"
	"	addiu	$19, $19, %lo(ship_tab_p1)\n"
	"	jr	$31\n"
	"	nop\n"
	"1:	lui	$19, %hi(ship_tab_p2)\n"
	"	jr	$31\n"
	"	addiu	$19, $19, %lo(ship_tab_p2)\n"
	".size ship_popup_tab, . - ship_popup_tab\n"
	/* type-D bomb 0x0011B460, replaces `lw t9,0(v1)` (table $gp-32640 + side * 4) at 0x0011B480; a2 = side.
	 * kind = (ship word >> 2) & 1; t9 = table[kind], t1 = kind + 1 (repeat count, read at 0x0011B4F4).
	 * Uses $at, t1, t9 (free there). */
	".globl bomb_d_kind\n"
	".type bomb_d_kind, @function\n"
	"bomb_d_kind:\n"
	"	sll	$9, $6, 9\n"
	"	sll	$1, $6, 7\n"
	"	addu	$9, $9, $1\n"
	"	sll	$1, $6, 4\n"
	"	addu	$9, $9, $1\n" /* side * 0x290 */
	"	lui	$1, 0x45\n"
	"	addu	$1, $1, $9\n"
	"	lw	$1, -15484($1)\n" /* 0x0044C384 + side * 0x290: ship word */
	"	srl	$1, $1, 2\n"
	"	andi	$1, $1, 1\n"
	"	addiu	$9, $1, 1\n"
	"	sll	$1, $1, 2\n"
	"	addu	$1, $1, $28\n"
	"	jr	$31\n"
	"	lw	$25, -32640($1)\n"
	".size bomb_d_kind, . - bomb_d_kind\n"
	".set pop\n");
