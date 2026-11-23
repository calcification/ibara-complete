/* Black Label (KURO) select screen, stage one (research/phase20): ship (straight / spread), then type A-D, as on the
 * arcade board, drawn from Black Label's own artwork (the user's ROM, patcher --bl-rom) with its own layout and
 * blend settings (bl_select_data.c, generated from MAME captures). Stage one: one steady frame per state (no
 * per-element animation, no fly-in, black instead of the girder background). Player 2 joins with
 * CONFIG > FIGHTER TYPE once gameplay resumes.
 *
 * Flow: a player start (0x001CE6E0, the code that writes the ship word; `dsll32` at 0x001CE718 -> sel_start_stub)
 * marks the side; the pause hook opens the screen for player 1 once the opening scene is ready and sets the pause byte
 * ($gp-28128), which stops the game update while the HUD pass still renders. The main loop then calls the pause
 * menu (0x00128E10, `jal` at 0x0012E778 -> sel_menu): sel_menu draws the screen and reads the pad instead, and
 * hands over to the real pause menu when the screen is not up. On confirm or when the 60-s timer runs out: ship
 * word = kind * 4 + type, FIGHTER TYPE config likewise, pause byte cleared. All of this is KURO-table code, so it
 * exists only inside KURO. Leaf code (no s-registers: called from the middle of the main loop).
 *
 * While it is up the draw pass skips the stage's 24 layers (sel_layers_stub): BL's screen covers the playfield, and
 * the GS texture cache then holds our pages next to the HUD's. (The freezes met on the way were not the cache: our
 * hooks were o32 code with 8-byte-aligned frames, and a thread switch inside our draw loops saved and restored the
 * main thread's registers with sq / lq on a misaligned stack — gp came back as garbage and the next sprite call
 * wrote through it. The hooks are n32 now: 16-byte frames.)
 */
#include "ibara_ps2.h"
#include "bl_select.h"

#define PAUSE_BYTE 0x00338F10u /* $gp-28128 */
#define PAD(port)  (0x00341FA0u + (port) * 0x50u) /* +0x08 buttons (edges), +0x0C directions (menu repeat) */
#define OFF_X      0x00338D08u
#define OFF_Y      0x00338D10u
#define SHIP_P1    (PS2_PLAYER_BASE + 4u)
#define FIGHTER_P1 0x004E5050u
#define ART_TAG    0x01F1FFF0u
#define PAUSE_MENU() GAME_CALL0(0x00128E10u)

#define BTN_UP 0x1u
#define BTN_DOWN 0x2u
#define BTN_LEFT 0x4u
#define BTN_RIGHT 0x8u
#define BTN_OK (0x10u | 0x20u) /* Circle or Cross */
#define SELECT_FRAMES (60u * 60u)

u32 ktex_init(void);
u32 ktex_claim(void);
void ktex_release(void);
u32 ktex_draw(u32 page, u32 px, u32 py, u32 pw, u32 ph, u32 flags, u32 tint, s32 x, s32 y);

u32 sel_pending[2] __attribute__((aligned(8))); /* set by sel_start_stub when a player starts */
u32 sel_active, sel_phase, sel_kind, sel_type, sel_timer;
static u32 last_dirs;

static u32 art_present(void)
{
	return EE_RAM(u32, ART_TAG) == 0x45534C42u && EE_RAM(u32, ART_TAG + 4u) == 0x5443454Cu && /* "BLSELECT" */
	       EE_RAM(u32, ART_TAG + 8u) == 0x5452412Du && EE_RAM(u32, ART_TAG + 12u) == 0x004E4F2Du; /* "-ART-ON\0" */
}

/* Scene 1 is the takeoff. The transition flag can still be set on entry, so only later scenes use the regular
 * pause condition. Scene 0 still belongs to the frontend or loader. */
static u32 pausable(void)
{
	const u8 scene = EE_RAM(u8, 0x00338E9Cu);
	return !EE_RAM(u8, 0x00338E7Cu) && !EE_RAM(u32, 0x00338EA8u) &&
	       (scene == 1u || (scene > 1u && !EE_RAM(u32, 0x00338F40u)));
}

static void sel_begin(void)
{
	u32 ship;
	if (sel_active || !sel_pending[0] || !pausable())
		return;
	if (!art_present()) {
		sel_pending[0] = sel_pending[1] = 0;
		return;
	}
	if (!ktex_init() || !ktex_claim())
		return;
	sel_pending[0] = sel_pending[1] = 0;
	ship = EE_RAM(u32, SHIP_P1);
	sel_kind = (ship >> 2) & 1u;
	sel_type = ship & 3u;
	sel_phase = 0;
	sel_timer = SELECT_FRAMES;
	last_dirs = EE_RAM(u32, PAD(0) + 0x0Cu);
	sel_active = 1;
	EE_RAM(u8, PAUSE_BYTE) = 1;
}

/* The retail pause check returns zero in scene 1 even if the pause byte is set. Return one while selecting so
 * the main loop skips the update pass that moves the ship and proceeds to drawing the menu. */
u32 sel_pause(void)
{
	sel_begin();
	return sel_active ? 1u : (u32)GAME_CALL0(0x0012C220u);
}

static void draw_state(u32 state, s32 ox, s32 oy)
{
	u32 i;
	for (i = sel_state_first[state]; i < sel_state_first[state + 1]; i++) {
		const struct sel_op *o = &sel_ops[i];
		const struct sel_sprite *s = &sel_sprites[o->sprite];
		ktex_draw(s->page, s->px, s->py, s->pw, s->ph, o->flags, o->tint, o->x + ox, o->y + oy);
	}
}

static void draw_digit(u32 d, s32 x, s32 y)
{
	const struct sel_sprite *s = &sel_sprites[sel_digit_sprite[d]];
	ktex_draw(s->page, s->px, s->py, s->pw, s->ph, sel_digit_flags, sel_digit_tint, x, y);
}

static void finish(void)
{
	const u32 v = sel_kind * 4u + sel_type;
	EE_RAM(u32, SHIP_P1) = v;    /* player 1: ship word = kind * 4 + type */
	EE_RAM(u32, FIGHTER_P1) = v; /* and KURO's FIGHTER TYPE value (side 0: same number) */
	sel_active = 0;
	ktex_release();
	EE_RAM(u8, PAUSE_BYTE) = 0;
}

/* in place of the pause menu call (0x0012E778): returns what the main loop expects (0 = carry on) */
u32 sel_menu(void)
{
	const s32 ox = EE_RAM(s32, OFF_X), oy = EE_RAM(s32, OFF_Y);
	u32 dirs, btn, edge, secs;
	if (!sel_active)
		return PAUSE_MENU();
	dirs = EE_RAM(u32, PAD(0) + 0x0Cu);
	btn = EE_RAM(u32, PAD(0) + 0x08u);
	if (sel_timer == SELECT_FRAMES)
		btn = 0; /* consume the difficulty-confirm edge on the first selection frame */
	edge = dirs & ~last_dirs;
	last_dirs = dirs;
	if (sel_phase == 0) {
		if (edge & (BTN_LEFT | BTN_RIGHT))
			sel_kind ^= 1u;
		if (btn & BTN_OK)
			sel_phase = 1;
	} else {
		if (edge & BTN_UP)
			sel_type = (sel_type + 3u) & 3u;
		if (edge & BTN_DOWN)
			sel_type = (sel_type + 1u) & 3u;
		if (btn & BTN_OK) {
			finish();
			return 0;
		}
	}
	if (sel_timer)
		sel_timer--;
	if (!sel_timer) {
		finish();
		return 0;
	}
	draw_state(SEL_HEAD, ox, oy);
	secs = (sel_timer + 59u) / 60u;
	draw_digit(secs / 10u, 280 + ox, 192 + oy);
	draw_digit(secs % 10u, 280 + ox, 208 + oy);
	draw_state(sel_phase == 0 ? SEL_SHIP_S + sel_kind : (sel_kind ? SEL_TYPE_P : SEL_TYPE_S) + sel_type, ox, oy);
	return 0;
}

__asm__(
	".set push\n.set noreorder\n.set noat\n"
	/* replaces `jal 0x00112500` at 0x0012E234 (draw pass, before the stage's 24-layer loop): while the select screen
	 * is up, 0x00112500 returns past the loop to the HUD calls (0x0012E424); nothing after the loop reads the loop's
	 * registers. Uses only $at and ra. */
	".globl sel_layers_stub\n"
	".type sel_layers_stub, @function\n"
	"sel_layers_stub:\n"
	"	lui	$1, %hi(sel_active)\n"
	"	lw	$1, %lo(sel_active)($1)\n"
	"	beqz	$1, 1f\n"
	"	nop\n"
	"	lui	$31, 0x0012\n"
	"	ori	$31, $31, 0xE424\n"
	"1:	j	0x00112500\n"
	"	nop\n"
	".size sel_layers_stub, . - sel_layers_stub\n"
	/* replaces `jal 0x0013BE30` at 0x0012E43C (the HUD pass's last call: the retail NOW LOADING banner, drawn while
	 * its fade $gp-28936 is non-zero): skipped while the select screen is up. The fade runs elsewhere (0x0013BFA0), so
	 * the banner is normally gone when the screen closes. Uses only $at. */
	".globl sel_banner_stub\n"
	".type sel_banner_stub, @function\n"
	"sel_banner_stub:\n"
	"	lui	$1, %hi(sel_active)\n"
	"	lw	$1, %lo(sel_active)($1)\n"
	"	bnez	$1, 1f\n"
	"	nop\n"
	"	j	0x0013BE30\n"
	"	nop\n"
	"1:	jr	$31\n"
	"	nop\n"
	".size sel_banner_stub, . - sel_banner_stub\n"
	/* replaces `dsll32 a0,t0,0x10` at 0x001CE718 (player start; t0 = side 0 / 1): same result, and marks the side.
	 * Uses only $at (ra is non-zero: stored as the flag). */
	".globl sel_start_stub\n"
	".type sel_start_stub, @function\n"
	"sel_start_stub:\n"
	"	dsll32	$4, $8, 0x10\n"
	"	lui	$1, %hi(sel_pending)\n"
	"	bnez	$8, 1f\n"
	"	nop\n"
	"	jr	$31\n"
	"	sw	$31, %lo(sel_pending)($1)\n"
	"1:	jr	$31\n"
	"	sw	$31, %lo(sel_pending + 4)($1)\n"
	".size sel_start_stub, . - sel_start_stub\n"
	".set pop\n");
