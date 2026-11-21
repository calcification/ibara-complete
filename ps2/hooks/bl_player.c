/* Black Label player rules for the PS2 engine (BLACK LABEL build only), called once per frame per active side
 * from xtc_frame(). */
#include "ibara_ps2.h"

/* BL pod formation per weapon (BL 0C077140 copies table 0C17F51B[weapon][pod] into the player's three pod bytes on
 * every pickup/change; measured in MAME). PS2 keeps the same three bytes at +0x26A..+0x26C, but Arrange sets them
 * from the formation the player picks (table 0x00212FF0, formation button), which the BLACK LABEL build disables.
 * Weapon ids as PS2/BL: 0 rocket, 1 burner, 2 gatling, 3 homing, 4 napalm, 5 MG, 6 5-way. */
static const u8 bl_pod_formation[7][3] = {
	{2, 2, 2}, {4, 4, 0}, {0, 0, 0}, {3, 3, 7}, {1, 1, 1}, {2, 2, 2}, {4, 4, 2},
};

void bl_player_frame(u32 rec)
{
	const u8 w = EE_RAM(u8, rec + 0x270);
	unsigned i;
	if (w >= 7)
		return;
	for (i = 0; i < 3; i++)
		EE_RAM(u8, rec + 0x26A + i) = bl_pod_formation[w][i];
}
