/* Black Label player rules for the PS2 engine (BLACK LABEL build only), called once per frame per active side
 * from xtc_frame(). */
#include "ibara_ps2.h"

/* BL pod formation per weapon (BL 0C077140 copies table 0C17F51B[weapon][pod] into the player's three pod bytes on
 * every pickup/change; measured in MAME). PS2 keeps the same three bytes at +0x26A..+0x26C, but Arrange sets them
 * from the formation the player picks (table 0x00212FF0, formation button), which the BLACK LABEL build disables.
 * Weapon ids as PS2/BL: 0 rocket, 1 burner, 2 gatling, 3 homing, 4 napalm, 5 MG, 6 5-way. */
static const u8 bl_pod_formation[7][3] __attribute__((unused)) = {
	{2, 2, 2}, {4, 4, 0}, {0, 0, 0}, {3, 3, 7}, {1, 1, 1}, {2, 2, 2}, {4, 4, 2},
};

/* DISABLED by default (define BL_POD_FORMATION to enable): BL's pod codes do not mean the same as PS2's. Phase 16:
 * BL's MG pods (code 2) aim at enemies (shot angles vary, -3.4..+1.4 px/frame sideways at 8 px/frame), while PS2's
 * code 2 is a fixed +/-34 degree spread and PS2 code 1 turns the pods back to straight ahead; no PS2 code aims. The
 * codes need BL's pod handler (0C0779E0 region) mapped before this table can be used. */
void bl_player_frame(u32 rec)
{
#if !defined(BL_POD_FORMATION) && !defined(BL_POD_TEST)
	(void)rec;
	return;
#else
	const u8 w = EE_RAM(u8, rec + 0x270);
	unsigned i;
	if (w >= 7)
		return;
	for (i = 0; i < 3; i++)
#ifdef BL_POD_TEST /* TEST BUILDS ONLY: force one PS2 pod code to compare behaviours */
		EE_RAM(u8, rec + 0x26A + i) = BL_POD_TEST;
#else
		EE_RAM(u8, rec + 0x26A + i) = bl_pod_formation[w][i];
#endif
#endif
}

/* BL pods aim while the shot is held (research/phase16, BL pod handler 0C0779B0): once BL's held-shot counter
 * (+0x270) reaches 8, every pod takes a target enemy (0C0769D0, kept in the pod's +0x28) and points at it
 * (atan2 0C068E60 into the pod's target angle +0x26), whatever its weapon's formation; with no target it keeps the
 * formation's angle. PS2 has the same aiming as pod code 1 (Arrange's aim lock: target 0x00137DA0 into +0x28, atan2
 * 0x00136CB0 into +0x26). The pod handler reads each pod's code at 0x001342D8 (`lbu a0, 0x26A(v1)`); in KURO that load
 * becomes `jal pod_mode_entry`, which answers 1 while the PS2 held counter ($gp-28068, 0..8, kept counting by the
 * held-fire patch) is 8. Difference: with no enemy on screen PS2's code 1 points straight ahead instead of keeping
 * the formation. Uses a0 and $at only; s2 = the pod's code address (set in the call's delay slot). */
__asm__(
	".set push\n.set noreorder\n.set noat\n"
	".globl pod_mode_entry\n"
	".type pod_mode_entry, @function\n"
	"pod_mode_entry:\n"
	"	lw	$1, -28068($28)\n"
	"	addiu	$1, $1, -8\n"
	"	bnez	$1, 1f\n"
	"	lbu	$4, 0($18)\n"
	"	li	$4, 1\n"
	"1:	jr	$31\n"
	"	nop\n"
	".size pod_mode_entry, . - pod_mode_entry\n"
	".set pop\n");
