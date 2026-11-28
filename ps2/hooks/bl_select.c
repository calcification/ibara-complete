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

/* Three slots are drawn (header, player 1, player 2 / join panel), each in a state it entered at some frame; every
 * track picks its sample from the frames since that entry (research/phase20 "Animation"). */
static u32 slot_state[3], slot_time[3];
/* BL's confirm (research/phase20 "Confirm"): per side the frames since it confirmed + 1 (the ship flash), and the
 * frames since every side confirmed + 1 (the panels fade out from frame 34; the screen closes at 64) */
static u32 flash_c[2], out_c;

static void slot_enter(u32 slot, u32 state)
{
	slot_state[slot] = state;
	slot_time[slot] = 0;
}


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
	flash_c[s] = 0;
	sel_kind[s] = (value >> 2) & 1u;
	sel_type[s] = value & 3u;
	last_dirs[s] = EE_RAM(u32, PAD(s) + 0x0Cu);
}

static void sel_begin(void)
{
	/* BL's select screen sits over the running stage 1 opening (research/phase20 "Stage two"): wait until the PS2's
	 * NOW LOADING fade ($gp-28936) is over and the launch pad is drawn, then hold the game there */
	if (sel_active || !(sel_pending[0] || sel_pending[1]) || !pausable()
#ifndef SEL_EARLY_TEST
	    || EE_RAM(u32, 0x00338BE8u)
#endif
	    )
		return;
	if (!art_present()) {
		sel_pending[0] = sel_pending[1] = 0;
		return;
	}
	if (!ktex_init() || !ktex_claim())
		return;
	/* the side(s) that started (BL: either Start button; the other side shows its join panel, research/phase20
	 * "Side select") */
	sel_on[0] = sel_on[1] = 0;
	slot_enter(0, SEL_HEAD);
	slot_enter(1, SEL_JOIN_P1);
	slot_enter(2, SEL_JOIN_P2);
	if (sel_pending[0]) {
		side_start(0, EE_RAM(u32, SHIP_P1));
		slot_enter(1, sel_kind[0] ? SEL_SHIP_P : SEL_OPEN);
	}
	if (sel_pending[1]) {
		const u32 cfg = EE_RAM(u32, FIGHTER(1));
		side_start(1, cfg < 8u ? cfg : 0u);
		slot_enter(2, sel_kind[1] ? SEL_SHIP_P2 : SEL_OPEN2);
	}
	sel_pending[0] = sel_pending[1] = 0;
	sel_timer = SELECT_FRAMES;
	sel_active = 1;
	out_c = 0;
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

/* 0-3 for a type state (A-D), -1 otherwise */
static s32 type_of(u32 state)
{
	if (state >= SEL_TYPE_S && state < SEL_TYPE_S + 8u)
		return (s32)((state - SEL_TYPE_S) & 3u);
	if (state >= SEL_TYPE_S2 && state < SEL_TYPE_S2 + 8u)
		return (s32)((state - SEL_TYPE_S2) & 3u);
	return -1;
}

/* frames until every track of a state has played its transition */
static u32 intro_frames(u32 state)
{
	u32 i, n = 0;
	for (i = sel_state_first[state]; i < sel_state_first[state + 1]; i++)
		if (sel_tracks[sel_state_refs[i]].intro > n)
			n = sel_tracks[sel_state_refs[i]].intro;
	return 2u * n;
}

static void draw_slot(u32 slot, u32 state, s32 ox, s32 oy, u32 flash, u32 fade)
{
	u32 i, k, ship;
	/* the screen's opening / player 2's joining run into the straight ship's state: keep their own tracks */
	if (!(slot_state[slot] == SEL_OPEN && state == SEL_SHIP_S) && !(slot_state[slot] == SEL_OPEN2 && state == SEL_SHIP_S2) &&
	    slot_state[slot] != state) {
		const s32 from = type_of(slot_state[slot]), to = type_of(state);
		slot_enter(slot, state);
		/* The captures stepped A -> B -> C -> D with Down: type A's transition is the panel sliding in from the ship
		 * screen, and B-D's first samples still show the type above (cursor and info). On BL a type change just swaps
		 * the panel's content (MAME: wrap D -> A and Up A -> D), so any type change, and entering B-D from the ship
		 * screen, starts after the transition. */
		if (to >= 0 && (from >= 0 || to > 0))
			slot_time[slot] = intro_frames(state);
	}
	k = slot_time[slot]++ >> 1;
	state = slot_state[slot];
	ship = sel_state_first[state] + sel_state_ship[state];
	for (i = sel_state_first[state]; i < sel_state_first[state + 1]; i++) {
		const struct sel_track *t = &sel_tracks[sel_state_refs[i]];
		const struct sel_sprite *s = &sel_sprites[t->sprite];
		const struct sel_rec *r;
		u32 n = k;
		if (n >= t->intro) {
			if (!t->loop)
				continue;
			n = t->intro + (n - t->intro) % t->loop;
		}
		r = &sel_recs[sel_samples[t->seq + n]];
		if (r->flags == 255u)
			continue;
		{
			u32 fl = sel_flags[r->flags], tint = sel_tints[r->tint];
			const s32 x = t->x + r->dx + ox, y = t->y + r->dy + oy;
			if (fade < 255u) { /* both blend alphas scaled; unblended elements go at half way */
				if (!(fl & 0xFFFFu) && fade < 0x80u)
					continue;
				fl = (fl & 0xFFFF0000u) | ((fl >> 8 & 0xFFu) * fade / 255u) << 8 | (fl & 0xFFu) * fade / 255u;
			}
			if (i == ship && flash >= 2u) { /* the ship lights up, tint 252 down to 132 */
				const u32 b = flash >= 32u ? 132u : 252u - 8u * ((flash - 2u) >> 1);
				tint = b << 16 | b << 8 | b;
			}
			ktex_draw(s->page, s->px, s->py, s->pw, s->ph, fl, tint, x, y);
			if (i == ship && flash >= 3u && flash <= 32u) { /* and a white additive copy fades from alpha 0xE8 */
				const u32 a = 0xE8u - 0x10u * ((flash - 3u) >> 1);
				ktex_draw(s->page, s->px, s->py, s->pw, s->ph, 0x12070000u | a << 8 | a, 0xFFFFFFu, x, y);
			}
		}
	}
}

static void draw_digit(u32 d, s32 x, s32 y, u32 fade)
{
	const struct sel_sprite *s = &sel_sprites[sel_digit_sprite[d]];
	u32 fl = sel_digit_flags;
	if (fade < 255u)
		fl = (fl & 0xFFFF0000u) | ((fl >> 8 & 0xFFu) * fade / 255u) << 8 | (fl & 0xFFu) * fade / 255u;
	ktex_draw(s->page, s->px, s->py, s->pw, s->ph, fl, sel_digit_tint, x, y);
}

static u32 side_state(u32 s)
{
	const u32 ship = s ? SEL_SHIP_S2 : SEL_SHIP_S, ts = s ? SEL_TYPE_S2 : SEL_TYPE_S, tp = s ? SEL_TYPE_P2 : SEL_TYPE_P;
	return sel_phase[s] == 0 ? ship + sel_kind[s] : (sel_kind[s] ? tp : ts) + sel_type[s];
}

static void finish(void)
{
	u32 s;
	for (s = 0; s < 2u; s++) {
		const u32 v = sel_kind[s] * 4u + sel_type[s];
		if (!sel_on[s])
			continue;
		/* FIGHTER TYPE and the ship word (side * 4 XOR value, K25 / K38); a side that joined on the screen then gets
		 * what the retail join (0x0012C5E4) does: the player set-up */
		EE_RAM(u32, FIGHTER(s)) = v;
		if (EE_RAM(u32, REC(s))) {
			EE_RAM(u32, REC(s) + 4u) = v ^ (4u * s);
		} else {
			EE_RAM(u32, REC(s) + 4u) = v ^ (4u * s);
			PLAYER_JOIN(s);
			/* BL's two-player takeoff: both ships leave the launch pad together. The retail join starts the player
			 * in its entry (state +0x0C = 1, invincibility counter +0x27A = 0xA7: it flies in after the takeoff).
			 * With the other player already in the takeoff, take its takeoff step and counter; the side's own
			 * position and speed words stay (they place the ship on its side of the pad). research/phase20
			 * "Two-player takeoff". */
			if (EE_RAM(u32, REC(s ^ 1u))) {
				EE_RAM(u32, REC(s) + 0x0Cu) = EE_RAM(u32, REC(s ^ 1u) + 0x0Cu);
				EE_RAM(u32, REC(s) + 0x278u) = EE_RAM(u32, REC(s ^ 1u) + 0x278u);
			}
		}
	}
	sel_active = 0;
	sel_on[0] = sel_on[1] = 0;
	ktex_release();
	EE_RAM(u8, PAUSE_BYTE) = 0;
	if (sel_bgm_on) {
		/* hand the music back: the stage's current track if it has one; otherwise fade the theme out as BL's opening
		 * does (script FF26, sound command (0, 16); research/phase25) with the PS2's own fade 0x0010F570(0, 16), the
		 * one its scene scripts use (0x001150C0): one volume step every 16 frames, then the stream stops; the stage's
		 * music starts later from its script */
		const u32 t = EE_RAM(u32, BGM_TRACK);
		sel_bgm_on = 0;
		if (t >= 1u && t <= 16u)
			BGM_TRACK_START(t);
		else
			GAME_CALL2(0x0010F570u, 0, 16);
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
		if (btn & BTN_OK) {
			sel_phase[s] = 2;
			flash_c[s] = 1;
		}
	}
	return sel_phase[s] == 2;
}

/* in place of the pause menu call (0x0012E778): returns what the main loop expects (0 = carry on) */
u32 sel_menu(void)
{
	const s32 ox = EE_RAM(s32, OFF_X), oy = EE_RAM(s32, OFF_Y);
	const u32 first = sel_timer == SELECT_FRAMES;
	u32 done, secs, s, fade;
	if (!sel_active)
		return PAUSE_MENU();
	{ /* a replay plays back: its recorded ships, confirmed at once (ps2/hooks/rpl.c) */
		u32 f[2], rpl_play_fighters(u32 *f);
		if (rpl_play_fighters(f)) {
			for (s = 0; s < 2u; s++)
				if (sel_on[s]) {
					sel_kind[s] = f[s] >> 2 & 1u;
					sel_type[s] = f[s] & 3u;
				}
			finish();
			return 0;
		}
	}
	for (s = 0; s < 2u && !out_c; s++) /* the free side joins with Start: starts on its CONFIG fighter type */
		if (!sel_on[s] && !EE_RAM(u32, REC(s)) && (EE_RAM(u16, REC(s) + REC_INPUT) & 0x200u)) {
			const u32 cfg = EE_RAM(u32, FIGHTER(s));
			side_start(s, cfg < 8u ? cfg : 0u);
			slot_enter(1u + s, s ? (sel_kind[1] ? SEL_SHIP_P2 : SEL_OPEN2) : (sel_kind[0] ? SEL_SHIP_P : SEL_OPEN));
		}
	if (!out_c) {
		done = 1;
		for (s = 0; s < 2u; s++)
			if (sel_on[s])
				done &= side_input(s, first);
		if (sel_timer)
			sel_timer--;
		if (done || !sel_timer) { /* everyone confirmed, or the time is up: BL's confirm, then the game */
			for (s = 0; s < 2u; s++)
				if (sel_on[s] && sel_phase[s] != 2u) {
					sel_phase[s] = 2;
					flash_c[s] = 1;
				}
			out_c = 1;
		}
	} else if (++out_c > 64u) {
		finish();
		return 0;
	}
	for (s = 0; s < 2u; s++)
		if (flash_c[s])
			flash_c[s]++;
	fade = out_c > 35u ? (0xF7u > 0x10u * ((out_c - 35u) >> 1) ? 0xF7u - 0x10u * ((out_c - 35u) >> 1) : 0) : 255u;
	draw_slot(0, SEL_HEAD, ox, oy, 0, fade);
	secs = (sel_timer + 59u) / 60u;
	draw_digit(secs / 10u, 280 + ox, 192 + oy, fade);
	draw_digit(secs % 10u, 280 + ox, 208 + oy, fade);
	draw_slot(1, sel_on[0] ? side_state(0) : SEL_JOIN_P1, ox, oy, sel_on[0] && flash_c[0] ? flash_c[0] - 2u : 0, fade);
	draw_slot(2, sel_on[1] ? side_state(1) : SEL_JOIN_P2, ox, oy, sel_on[1] && flash_c[1] ? flash_c[1] - 2u : 0, fade);
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
