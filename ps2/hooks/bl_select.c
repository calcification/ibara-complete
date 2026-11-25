/* Black Label (KURO) select screen, stage one (research/phase20): ship (straight / spread), then type A-D, as on the
 * arcade board, drawn from Black Label's own artwork (the user's ROM, patcher --bl-rom) with its own layout and
 * blend settings (bl_select_data.c, generated from MAME captures). Stage one: one steady frame per state (no
 * per-element animation, no fly-in, black instead of the girder background). Player 2 joins on the screen with
 * Start (its own panel; the free side shows the join panel) or later in the game with CONFIG > FIGHTER TYPE.
 *
 * Flow: a player start (0x001CE6E0, the code that writes the ship word; `dsll32` at 0x001CE718 -> sel_start_stub)
 * marks the side; the pause hook opens the screen for player 1 once the opening scene is ready and sets the pause byte
 * ($gp-28128), which stops the game update while the HUD pass still renders. The main loop then calls the pause
 * menu (0x00128E10, `jal` at 0x0012E778 -> sel_menu): sel_menu draws the screen and reads the pad instead, and
 * hands over to the real pause menu when the screen is not up. On confirm or when the 60-s timer runs out: ship
 * word = kind * 4 + type, FIGHTER TYPE config likewise, pause byte cleared. All of this is KURO-table code, so it
 * exists only inside KURO. Leaf code (no s-registers: called from the middle of the main loop).
 *
 * As on BL, the stage stays drawn behind the screen: BL's select screen sits over the running stage 1 opening (the
 * launch pad; research/phase20 "Stage two"), so the screen opens once the PS2's NOW LOADING fade is over and the
 * launch pad is up, and the stage's layers keep drawing under our panels (a 60-s PCSX2 run with both players showed
 * no texture-cache trouble; the layers used to be skipped). (The freezes met on the way were not the cache: our
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

/* Black Label's ship-select theme (BL: sequence 0 -> phrase 0, 16 kHz AMM). The patcher (--bl-rom with the
 * sound ROMs u23 / u24) decodes it, stores it as a BG00 stream in IBARAR.PDM and writes its archive entry here
 * (0xFFFFFFFF: no theme on the disc). research/phase23. */
struct sel_music_slot {
	char tag[16];
	u32 entry;  /* archive entry of the stream */
	u32 volume; /* the track record's volume (retail tracks 0x46-0x6E) */
};
struct sel_music_slot sel_music = {"BLSELECT-MUS-01", 0xFFFFFFFFu, 0x58u};
#define BGM_TRACK  0x00338B80u /* $gp-29040: the track number 0x001371A0 last started (0 = none) */
#define BGM_START(rec) GAME_CALL4(0x0010F760u, 0, (rec), 12u, 0) /* request stream (a0 0, record, 12 bytes) */
#define BGM_TRACK_START(t) GAME_CALL2(0x001371A0u, (t), 0)       /* track 1-16 by number; 0 stops */
static struct { s16 entry, volume; u32 zero; u16 loop, pad; } sel_bgm __attribute__((aligned(4)));
static u32 sel_bgm_on;

u32 sel_pending[2] __attribute__((aligned(8))); /* set by sel_start_stub when a player starts */
u32 sel_active, sel_timer;
/* Per side (0 = player 1, 1 = player 2): on the screen, phase (0 ship, 1 type, 2 confirmed), ship kind (0 straight,
 * 1 spread), type 0-3, last direction word (edges). Player 2 joins with Start while the screen is up, as on the
 * arcade board (MAME: the free side shows the 参戦可能 join panel; a player who joins later in the game gets no
 * screen). */
u32 sel_on[2], sel_phase[2], sel_kind[2], sel_type[2];
static u32 last_dirs[2];

#define REC(s)       (PS2_PLAYER_BASE + (s) * PS2_PLAYER_STRIDE)
#define REC_INPUT    0x24Eu  /* mapped input, newly pressed (u16): 0x200 = Start */
#define FIGHTER(s)   (FIGHTER_P1 + 4u * (s))
#define PLAYER_JOIN(s) GAME_CALL2(0x0012D840u, (s), 0) /* the retail join's player set-up (0x0012C608) */

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

static void side_start(u32 s, u32 value)
{
	sel_on[s] = 1;
	sel_phase[s] = 0;
	sel_kind[s] = (value >> 2) & 1u;
	sel_type[s] = value & 3u;
	last_dirs[s] = EE_RAM(u32, PAD(s) + 0x0Cu);
}

static void sel_begin(void)
{
	/* BL's select screen sits over the running stage 1 opening (research/phase20 "Stage two"): wait until the PS2's
	 * NOW LOADING fade ($gp-28936) is over and the launch pad is drawn, then hold the game there */
	if (sel_active || !sel_pending[0] || !pausable() || EE_RAM(u32, 0x00338BE8u))
		return;
	if (!art_present()) {
		sel_pending[0] = sel_pending[1] = 0;
		return;
	}
	if (!ktex_init() || !ktex_claim())
		return;
	sel_pending[0] = sel_pending[1] = 0;
	side_start(0, EE_RAM(u32, SHIP_P1));
	sel_on[1] = 0;
	sel_timer = SELECT_FRAMES;
	sel_active = 1;
	EE_RAM(u8, PAUSE_BYTE) = 1;
	sel_bgm_on = 0;
	if (sel_music.entry < 0x8000u) {
		sel_bgm.entry = (s16)sel_music.entry;
		sel_bgm.volume = (s16)sel_music.volume;
		sel_bgm.zero = 0;
		sel_bgm.loop = 1;
		BGM_START((u32)&sel_bgm);
		sel_bgm_on = 1;
	}
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

static u32 side_state(u32 s)
{
	const u32 ship = s ? SEL_SHIP_S2 : SEL_SHIP_S, ts = s ? SEL_TYPE_S2 : SEL_TYPE_S, tp = s ? SEL_TYPE_P2 : SEL_TYPE_P;
	return sel_phase[s] == 0 ? ship + sel_kind[s] : (sel_kind[s] ? tp : ts) + sel_type[s];
}

static void finish(void)
{
	const u32 v = sel_kind[0] * 4u + sel_type[0];
	EE_RAM(u32, SHIP_P1) = v;    /* player 1: ship word = kind * 4 + type */
	EE_RAM(u32, FIGHTER_P1) = v; /* and KURO's FIGHTER TYPE value (side 0: same number) */
	if (sel_on[1] && !EE_RAM(u32, REC(1))) {
		/* player 2 joined on the screen: what the retail join (0x0012C5E4) does for side 1 - FIGHTER TYPE, the
		 * ship word (KURO's join stores the value XOR 4 for side 1, K38), then the player set-up */
		const u32 v2 = sel_kind[1] * 4u + sel_type[1];
		EE_RAM(u32, FIGHTER(1)) = v2;
		EE_RAM(u32, REC(1) + 4u) = v2 ^ 4u;
		PLAYER_JOIN(1);
	}
	sel_active = 0;
	sel_on[1] = 0;
	ktex_release();
	EE_RAM(u8, PAUSE_BYTE) = 0;
	if (sel_bgm_on) { /* hand the music back: the stage's current track, or silence until its script starts one */
		const u32 t = EE_RAM(u32, BGM_TRACK);
		sel_bgm_on = 0;
		BGM_TRACK_START(t >= 1u && t <= 16u ? t : 0u);
	}
}

/* One side's input; returns 1 once it has confirmed. */
static u32 side_input(u32 s, u32 first)
{
	const u32 dirs = EE_RAM(u32, PAD(s) + 0x0Cu);
	const u32 btn = first ? 0 : EE_RAM(u32, PAD(s) + 0x08u); /* first frame: drop the GAME START edge */
	const u32 edge = dirs & ~last_dirs[s];
	last_dirs[s] = dirs;
	if (sel_phase[s] == 0) {
		if (edge & (BTN_LEFT | BTN_RIGHT))
			sel_kind[s] ^= 1u;
		if (btn & BTN_OK)
			sel_phase[s] = 1;
	} else if (sel_phase[s] == 1) {
		if (edge & BTN_UP)
			sel_type[s] = (sel_type[s] + 3u) & 3u;
		if (edge & BTN_DOWN)
			sel_type[s] = (sel_type[s] + 1u) & 3u;
		if (btn & BTN_OK)
			sel_phase[s] = 2;
	}
	return sel_phase[s] == 2;
}

/* in place of the pause menu call (0x0012E778): returns what the main loop expects (0 = carry on) */
u32 sel_menu(void)
{
	const s32 ox = EE_RAM(s32, OFF_X), oy = EE_RAM(s32, OFF_Y);
	const u32 first = sel_timer == SELECT_FRAMES;
	u32 done, secs;
	if (!sel_active)
		return PAUSE_MENU();
	if (!sel_on[1] && !EE_RAM(u32, REC(1)) && (EE_RAM(u16, REC(1) + REC_INPUT) & 0x200u)) {
		const u32 cfg = EE_RAM(u32, FIGHTER(1));
		side_start(1, cfg < 8u ? cfg : 0u); /* player 2 joins: starts on its CONFIG fighter type */
	}
	done = side_input(0, first);
	if (sel_on[1])
		done &= side_input(1, first);
	if (sel_timer)
		sel_timer--;
	if (done || !sel_timer) {
		finish();
		return 0;
	}
	draw_state(SEL_HEAD, ox, oy);
	secs = (sel_timer + 59u) / 60u;
	draw_digit(secs / 10u, 280 + ox, 192 + oy);
	draw_digit(secs % 10u, 280 + ox, 208 + oy);
	draw_state(side_state(0), ox, oy);
	draw_state(sel_on[1] ? side_state(1) : SEL_JOIN_P2, ox, oy);
	return 0;
}

__asm__(
	".set push\n.set noreorder\n.set noat\n"
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
