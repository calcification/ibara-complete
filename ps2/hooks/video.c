/* Screen-mode aware video ("auto" profile): Yoko keeps the retail interlaced output, Tate R / Tate L switch to
 * 240p progressive. Texture filtering is off in every mode (static edit at 0x001AF11C, TEX1 MMAG/MMIN 0x60 -> 0),
 * and the Tate display tables carry the 240p crop statically (0x001DD200 / 0x001DD240; Yoko's 0x001DD1C0 stays
 * retail). The display code picks those tables by the screen mode itself (0x0010E554).
 *
 * What cannot be static because it lives in code or is set once at boot: the 4 half-pixel offset immediates and the
 * 3 field-state stores of the cave-ps2-240p beta, and the scan mode set by the boot GS reset. This
 * hook runs after the per-frame display call (main loop 0x0010BC78 -> 0x0010E480) on every screen and, when the
 * mode crosses between Yoko and Tate, swaps those words, flushes the caches and reprograms the CRTC through the
 * BIOS SetGsCrt (interlaced field mode for Yoko, progressive for Tate; NTSC or PAL as the game chose at boot).
 *
 * The library's two display environments (0x004F9490 and 0x004F94B8: PMODE, SMODE2, DISPFB, DISPLAY, BGCOLOR,
 * written to the GS every frame) are computed once at boot for the boot scan mode. Every frame the hook keeps them
 * consistent with the mode: Tate = SMODE2 2 and half the DISPLAY height and DY (retail 448 lines / DY 50 -> 224 /
 * 25, exactly what the cave-ps2-240p build produces), Yoko = SMODE2 3 and the retail values. Keyed on the current
 * height, so a recomputed environment (e.g. after SCREEN ADJUST) is corrected again.
 */
#include "ibara_ps2.h"

#pragma GCC optimize("Os") /* the frontend executable only has ~830 bytes of disc slack for this hook */

#define SCREEN_MODE 0x00338AF0u /* $gp-29184: mode used by the display code (0 Yoko, 1 Tate R, 2 Tate L) */
#define SCREEN_SETTING 0x00338F68u /* $gp-28040: the OPTION menu value (the menu copies it to SCREEN_MODE) */
#define FRONTEND_STATE 0x00338F58u /* Mode Select is reachable after autoload ends */
/* Screen mode carried across the launcher <-> KURO executable switch (LoadExecPS2 reloads the game, whose memory
 * and settings start from defaults): the switching executable passes "S=<mode>" as an argument (launcher: its KURO
 * dispatcher, argv at 0x001D42F4 -> MODE_ARG; KURO: bl_return.c), and each executable reads its own arguments from
 * the start-up block that crt0 hands to SetupThread (0x004E52C0: argc, argv[]) and adopts the mode at start-up.
 * MODE_ARG lies in the zero padding after the retail code (launcher builder, research/phase04, which stores "S=0";
 * bl_return.c writes the "S=" in KURO); its digit is refreshed every frame so the argument carries the current mode. */
#define MODE_ARG    0x001D42F8u  /* "S=<screen mode digit><rank gauge digit>\0" (0x001D42F8-0x001D42FC) */

extern u32 opt_gauge;     /* options.c: RANK GAUGE setting, carried with the screen mode */
void opt_set(u32 on);
#define ARGS_BLOCK  0x004E52C0u
#define SETTINGS_RECORD 0x004956F4u /* screen mode in the settings record (card / defaults) */
#define VIDEO_STD   0x00337D00u /* $gp-32752 (s8): 2 selects omode 3 (PAL) in the boot GS reset (0x001AD238) */

/* Code words switched between Yoko (retail) and Tate (cave-ps2-240p beta): the 4 half-pixel offset immediates
 * (-8) and the 3 field-state stores (write $zero). The GS-reset interlace
 * flag (0x001AD250) is not switched: the reset only runs at boot, and SetGsCrt below sets the scan mode. */
static const u32 swap_addr[7] = {0x001AECD4u, 0x001AED3Cu, 0x001AED88u, 0x001AEDD4u,
				 0x001B29D4u, 0x001B2A60u, 0x001B2A80u};
static const u32 swap_word[2][7] = {
	{0x24AA7900u, 0x26527900u, 0x24427900u, 0x24427900u, 0xAF829574u, 0xAF839550u, 0xAF829574u}, /* Yoko */
	{0x24AA78F8u, 0x265278F8u, 0x244278F8u, 0x244278F8u, 0xAF809574u, 0xAF809550u, 0xAF809574u}, /* Tate */
};

/* All mutable state in one block (the frontend executable has only a few hundred bytes for this hook). */
static volatile struct {
	u32 tate;    /* current state; the executable boots in the retail (Yoko) state */
	u32 crt[2];  /* SetGsCrt arguments for the switch: interlace (also FFMD), omode */
	u32 carried; /* mode passed by the other executable: 0..2, 0xFF = none, 0xFE = not looked up yet */
} vs = {0u, {0u, 0u}, 0xFEu};

#define DISP_ENV0 0x004F9490u
#define DISP_ENV1 0x004F94B8u
#define DH_SPLIT  300u /* DISPLAY heights above this are interlaced-frame values (448 / 512), below progressive */

static void fix_one_env(u32 env, u32 tate)
{
	volatile u32 *e = (volatile u32 *)env; /* [2] SMODE2, [6] DISPLAY low (DY 12-22), [7] DISPLAY high (DH 12-22) */
	u32 dh = (e[7] >> 12) & 0x7FFu, dy = (e[6] >> 12) & 0x7FFu;

	if (!dh) /* not set up yet by the library (start-up): leave alone */
		return;
	if (tate == (dh >= DH_SPLIT)) { /* still the other mode's geometry */
		if (tate) { /* 448 lines (DH 447) / DY 50 -> 224 (DH 223) / DY 25 */
			dh >>= 1;
			dy >>= 1;
		} else {
			dh = dh * 2u + 1u;
			dy <<= 1;
		}
		e[6] = (e[6] & ~(0x7FFu << 12)) | dy << 12;
		e[7] = (e[7] & ~(0x7FFu << 12)) | dh << 12;
	} else if (!tate) {
		return; /* Yoko with retail values: nothing to do */
	}
	e[2] = tate ? 2u : 3u;
}


/* FlushCache(0), FlushCache(2), then SetGsCrt(vs.crt[0], vs.crt[1], vs.crt[0]). One asm block so that nothing
 * lives in a register across the kernel calls (they may overwrite every caller-saved register), and no callee-saved
 * register is needed (the video stub does not preserve them). */
static void switch_crt(void)
{
	__asm__ __volatile__(
		".set noat\n"
		"move $4, $0\n\tli $3, 100\n\tsyscall\n"
		"li $4, 2\n\tli $3, 100\n\tsyscall\n"
		"lui $1, %%hi(vs+4)\n\tlw $4, %%lo(vs+4)($1)\n"
		"lui $1, %%hi(vs+8)\n\tlw $5, %%lo(vs+8)($1)\n"
		"move $6, $4\n\tli $3, 2\n\tsyscall\n"
		".set at\n"
		: : : "$1", "v0", "v1", "a0", "a1", "a2", "a3", "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7",
		      "t8", "t9", "memory");
}


static void fix_display_env(u32 tate)
{
	fix_one_env(DISP_ENV0, tate);
	fix_one_env(DISP_ENV1, tate);
}


/* Replaces `jal 0x0010FE20` (store the applied screen mode, $gp-29184) at the two start-up settings loads
 * (0x001D1B24, 0x001D3CD4: boot and memory-card load, after 0x0013E680 copied the settings record to the globals);
 * also called on the first frame (no card: those loads never run). The mode passed as an "S=<digit>" argument
 * by the other executable overrides them; OPTION changes go through 0x001CD770 and stand. Leaf, temporaries only. */
void video_apply(u32 mode)
{
	if (vs.carried == 0xFEu) {
		vs.carried = 0xFFu;
		if (EE_RAM(u32, ARGS_BLOCK) == 2u) {
			const u8 *arg = (const u8 *)EE_RAM(u32, ARGS_BLOCK + 8u);
			if (arg[0] == 'S' && arg[1] == '=' && (u8)(arg[2] - '0') <= 2u &&
			    (arg[3] == 0 || ((u8)(arg[3] - '0') <= 1u && arg[4] == 0))) {
				vs.carried = arg[2] - (u8)'0';
				if (arg[3] == '0')
					opt_set(0u); /* RANK GAUGE OFF in the other executable (options.c) */
			}
		}
	}
	if (vs.carried <= 2u) {
		mode = vs.carried;
		EE_RAM(u32, SETTINGS_RECORD) = mode;
		EE_RAM(u32, SCREEN_SETTING) = mode;
	}
	EE_RAM(u32, SCREEN_MODE) = mode;
}

void video_frame(void)
{
	u32 m, tate;
	unsigned i;

	if (vs.carried == 0xFEu)
		video_apply(EE_RAM(u32, SCREEN_MODE));
	if (EE_RAM(u32, FRONTEND_STATE) == 1u)
		vs.carried = 0xFFu;
	EE_RAM(u8, MODE_ARG + 2u) = (u8)('0' + (EE_RAM(u32, SCREEN_MODE) & 3u));
	EE_RAM(u8, MODE_ARG + 3u) = (u8)('0' + opt_gauge);
	m = EE_RAM(u32, SCREEN_MODE);
	tate = (m == 1u || m == 2u);
	if (tate != vs.tate) {
		vs.tate = tate; /* committed first: nothing is kept in registers across the kernel calls */
		for (i = 0; i < 7u; i++)
			EE_RAM(u32, swap_addr[i]) = swap_word[tate][i];
		vs.crt[0] = tate ? 0u : 1u;
		vs.crt[1] = 2u + (EE_RAM(u8, VIDEO_STD) == 2u); /* omode 2 NTSC, 3 PAL (as the boot GS reset) */
		switch_crt();
		m = 4u; /* just switched */
	}
	/* Tate: keep the geometry progressive every frame. Yoko is left to the game (its loading screen, for one, uses a
	 * smaller display than the retail frame) except once, right after leaving Tate, to restore the retail geometry. */
	if (vs.tate || m == 4u)
		fix_display_env(vs.tate);
}
