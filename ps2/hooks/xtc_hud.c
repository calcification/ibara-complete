/* XTC counter on the HUD, drawn with the game's own text layer.
 *
 * The HUD prints into a character-cell buffer at 0x00346AB0 (rows of 32 u32 cells, colour | char), via
 * 0x00111460 (string: str, row, col, colour) and 0x0012C0E0 (number: value, row, col, colour; right-
 * aligned, 7 cells from col; buffer row = argument - 2). The per-frame score updater 0x0012C2E0 loops over both
 * player records and prints each score at row 39 by `jal 0x0012C0E0` at 0x0012C394 (Arcade) / 0x0012C3BC
 * (Arrange); this runs right after those calls. (0x0012CE1C/0x0012CF7C only run once, at HUD setup.)
 */
#include "ibara_ps2.h"

/* 0x00111460 (string, row, col, colour) and 0x0012C0E0 (value, row, col, colour) */
#define HUD_STR(s, row, col, colour) GAME_CALL4(0x00111460u, s, row, col, colour)
#define HUD_NUM(v, row, col, colour) GAME_CALL4(0x0012C0E0u, v, row, col, colour)

#ifndef XTC_HUD_ROW
#define XTC_HUD_ROW 36 /* score line is 39; 38 holds lives icons, 37 the padded stage name (cols 5-18) */
#endif
#define XTC_HUD_COL 2
#define XTC_HUD_COLOUR 0x80808000u

int xtc_shown(unsigned side);
static const char xtc_label[] = "XTC";
u32 xtc_hud_calls; /* debug: HUD passes seen */
int xtc_hud_last;  /* debug: last value printed */

static const int xtc_hud_col[2] = { XTC_HUD_COL, 18 }; /* under 1P's and 2P's scores */

#ifdef KURO_PRESENTATION
extern u32 sel_active;
static const char xtc_blank[] = "          "; /* label (3 cells) + value (7 cells) */
#else
/* BL weapon stock: current weapon (player +0x270, ids 0 rocket, 1 burner, 2 gatling, 3 homing, 4 napalm,
 * 5 machine gun, 6 5way; 0xFF none) shown after the XTC value, in BL's HUD spelling. */
static const char w_rocket[] = "ROCKET", w_burnar[] = "BURNAR", w_gatling[] = "GATLING", w_homing[] = "HOMING",
		  w_napalm[] = "NAPALM", w_mg[] = "M.G", w_5way[] = "5WAY", w_none[] = "       ";
static const char *const weapon_name[7] = { w_rocket, w_burnar, w_gatling, w_homing, w_napalm, w_mg, w_5way };
#define WEAPON_HUD_ROW (XTC_HUD_ROW - 1) /* the line under the XTC counter */
#endif

void xtc_hud(void)
{
	unsigned s;
	xtc_hud_calls++;
#ifdef KURO_PRESENTATION
	if (sel_active) {
		for (s = 0; s < 2; s++)
			HUD_STR(xtc_blank, XTC_HUD_ROW, xtc_hud_col[s], XTC_HUD_COLOUR);
		return;
	}
#endif
	for (s = 0; s < 2; s++) {
		if (EE_RAM(u32, PS2_PLAYER_BASE + s * PS2_PLAYER_STRIDE + PS2_PLAYER_FLAGS) == 0)
			continue; /* side not in the game: leave its HUD untouched */
		if (s == 0)
			xtc_hud_last = xtc_shown(0);
		HUD_STR(xtc_label, XTC_HUD_ROW, xtc_hud_col[s], XTC_HUD_COLOUR);
		HUD_NUM(xtc_shown(s), XTC_HUD_ROW, xtc_hud_col[s] + 3, XTC_HUD_COLOUR);
#ifndef KURO_PRESENTATION
		{
			const u8 w = EE_RAM(u8, PS2_PLAYER_BASE + s * PS2_PLAYER_STRIDE + 0x270);
			HUD_STR(w_none, WEAPON_HUD_ROW, xtc_hud_col[s], XTC_HUD_COLOUR);
			if (w < 7)
				HUD_STR(weapon_name[w], WEAPON_HUD_ROW, xtc_hud_col[s], XTC_HUD_COLOUR);
		}
#endif
	}
}
