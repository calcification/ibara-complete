/* K65: REPLAY in each mode's menu (research/phase47).
 *
 * The ARCADE MODE menu (also NOIR MODE's) is frontend state 2: labels from 0x002A9020 (4 rows), help text two lines
 * per row from 0x002A90E0, accept 0x10: row 0 GAME START (state 3), 1 PRACTICE, 2 CONFIG, 3 EXIT. Patched
 * (REPLAY_MENU_PATCHES) to 5 rows read from rm_label / rm_help, with EXIT at row 4; row 3 REPLAY is answered here.
 * rm_label / rm_help rows 0-2 are copied from the game's tables every frame (KURO switches some of their words).
 *
 * The list is the game's own memory card dialog look (panel 0x001CE830, text 0x001CEC40 as 0x001D05C0 draws them),
 * drawn after the menu each frame (the frontend frame's flush 0x001CA294 calls rm_flush); while it is open the menu's pad reads
 * (0x001C9438-0x001C9464) see nothing. It lists the replay saves BISLPM-66301R<mode><YYMMDDhhmm> of this mode,
 * newest first, with stage and score from each file's header; shot plays, bomb goes back. Playing loads the file
 * into the replay buffer (rpl.c), applies the recording's settings and starts the game as GAME START does. */
#include "ibara_ps2.h"

#define MAIN_STATE  0x00338B08u
#define FRONT_STATE 0x00338F58u /* $gp-28056 */
#define FRONT_ROW   0x0033948Cu /* $gp-26724 */
#define FRONT_ANIM  0x00338F64u /* $gp-28044 */
#define MENU_ROW    0x00339484u /* $gp-26732: the cursor row in a mode menu */
#define ARRANGE     0x00338F44u
#define LABELS      0x002A9020u
#define HELP        0x002A90E0u
#define PAD_REPEAT  0x0010DD90u
#define PAD_PRESSED 0x0010DDB0u
#define PANEL       0x001CE830u
#define TEXT        0x001CEC40u
#define TABLE       ((u8 *)0x01E90000u) /* sceMcGetDir entries, 64 bytes each */
#define HEADS       ((u32 *)0x01E98000u) /* the first 64 bytes of each replay file */
#define MAX_LIST    32u
#define SHOWN       7u

u32 mc_list(const char *pattern, void *table, u32 max);
u32 mc_load(const char *dir, const char *name, void *dst, u32 max);
u32 mc_busy(void);
s32 mc_error(void);
u32 mc_done(void);
u32 mc_loaded(void);
void mc_tick(void);
u8 *rpl_buffer(void);
u32 rpl_buffer_max(void);
u32 rpl_play_loaded(u32 size);
extern u32 kuro_on;

const char *rm_label[5];
u32 rm_help[10];
const char rm_replay_label[] = "REPLAY";
/* "保存したリプレイを" / "再生します。" */
const u8 rm_help1[] = "\x95\xDB\x91\xB6\x82\xB5\x82\xBD\x83\x8A\x83\x76\x83\x8C\x83\x43\x82\xF0";
const u8 rm_help2[] = "\x8D\xC4\x90\xB6\x82\xB5\x82\xDC\x82\xB7\x81\x42";
/* ARRANGE MODE's help text with REPLAY (options.c arr_desc's rows, REPLAY inserted at row 3) */
const char *const rm_arr_desc[10] = {
	(const char *)0x00302630u, (const char *)0x00301D70u, /* GAME START */
	(const char *)0x00301FA0u, (const char *)0x00301D70u, /* PRACTICE */
	(const char *)0x00302650u, (const char *)0x00301DE0u, /* CONFIG */
	(const char *)rm_help1, (const char *)rm_help2,       /* REPLAY */
	(const char *)0x00301E00u, (const char *)0x00301E20u, /* EXIT */
};
static const u8 t_head[] = "\x81\x40\x81\x40\x81\x40\x81\x40\x83\x8A\x83\x76\x83\x8C\x83\x43"; /* 　　　　リプレイ */
static const u8 t_load[] = "\x83\x81\x83\x82\x83\x8A\x81\x5B\x83\x4A\x81\x5B\x83\x68\x81\x69\x82\x6F\x82\x72\x82\x51\x81\x6A\x82\xF0\x83\x60\x83\x46\x83\x62\x83\x4E\x92\x86\x82\xC5\x82\xB7\x81\x42"; /* メモリーカード（ＰＳ２）をチェック中です。 */
static const u8 t_none[] = "\x83\x8A\x83\x76\x83\x8C\x83\x43\x82\xAA\x82\xA0\x82\xE8\x82\xDC\x82\xB9\x82\xF1\x81\x42"; /* リプレイがありません。 */
static const u8 t_fail[] = "\x83\x8D\x81\x5B\x83\x68\x82\xC9\x8E\xB8\x94\x73\x82\xB5\x82\xDC\x82\xB5\x82\xBD\x81\x42"; /* ロードに失敗しました。 */
static const u8 t_card[] = "\x83\x81\x83\x82\x83\x8A\x81\x5B\x83\x4A\x81\x5B\x83\x68\x81\x69\x82\x6F\x82\x72\x82\x51\x81\x6A\x82\xAA\x8D\xB7\x82\xB3\x82\xEA\x82\xC4\x82\xA2\x82\xDC\x82\xB9\x82\xF1\x81\x42"; /* メモリーカード（ＰＳ２）が差されていません。 */

enum { R_OFF, R_LIST, R_HEADS, R_SHOW, R_LOAD, R_MSG, R_START };
static u32 inject; /* a press the menu sees on port 0 next frame (starting a playback) */
u32 rpl_play_difficulty(void);
static u32 st, n, k, cur, top, wait;
static u32 back_to_menu; /* a playback started from here: come back to this menu (its state), on REPLAY */
static u32 menu_state;   /* 2 ARCADE / NOIR MODE, 9 ARRANGE MODE */
#define ARRANGE_MENU 9u
static const u8 *msg;
static u8 order[MAX_LIST];
static char pattern[24], dir[32];
static u8 line[SHOWN][64];

static void sync_tables(void)
{
	u32 i;
	for (i = 0; i < 3u; i++) {
		rm_label[i] = (const char *)EE_RAM(u32, LABELS + 4u * i);
		rm_help[2 * i] = EE_RAM(u32, HELP + 8u * i);
		rm_help[2 * i + 1] = EE_RAM(u32, HELP + 8u * i + 4u);
	}
	rm_label[3] = rm_replay_label;
	rm_help[6] = (u32)rm_help1;
	rm_help[7] = (u32)rm_help2;
	rm_label[4] = (const char *)EE_RAM(u32, LABELS + 12u); /* EXIT */
	rm_help[8] = EE_RAM(u32, HELP + 24u);
	rm_help[9] = EE_RAM(u32, HELP + 28u);
}

static const char *entry_name(u32 i) { return (const char *)(TABLE + 64u * order[i] + 0x20u); }

static u8 *fw(u8 *p, char c)
{
	if (c >= '0' && c <= '9') {
		*p++ = 0x82;
		*p++ = (u8)(0x4F + (c - '0'));
	} else if (c == '/') {
		*p++ = 0x81;
		*p++ = 0x5E;
	} else if (c == ':') {
		*p++ = 0x81;
		*p++ = 0x46;
	} else if (c >= 'A' && c <= 'Z') {
		*p++ = 0x82;
		*p++ = (u8)(0x60 + (c - 'A'));
	} else {
		*p++ = 0x81;
		*p++ = 0x40;
	}
	return p;
}

static u8 *fw_str(u8 *p, const char *s)
{
	while (*s)
		p = fw(p, *s++);
	return p;
}

static u8 *fw_num(u8 *p, u32 v)
{
	char b[12];
	u32 i = 11;
	b[i] = 0;
	do {
		b[--i] = (char)('0' + v % 10u);
		v /= 10u;
	} while (v && i);
	return fw_str(p, b + i);
}

/* "２６／１１／２８　１５：４２　ＳＴ３　　１２３４５６７" from the folder name and the header */
static void make_line(u8 *out, u32 i)
{
	const char *d = entry_name(i) + 14; /* after BISLPM-66301R<mode> */
	const u32 *h = HEADS + 16u * order[i];
	const u32 scene = h[10] >> 24, stage = scene >= 2u ? scene - 1u : 1u; /* end_tick */
	u8 *p = out;
	char t[3] = {0, 0, 0};
	u32 j;
	for (j = 0; j < 5u; j++) {
		t[0] = d[2 * j];
		t[1] = d[2 * j + 1];
		p = fw_str(p, t);
		if (j < 4u)
			p = fw(p, j < 2u ? '/' : j == 2u ? ' ' : ':');
	}
	p = fw_str(p, " ST");
	p = fw_num(p, stage);
	p = fw_str(p, "  ");
	p = fw_num(p, h[8]); /* end_score */
	*p = 0;
}

static void open_list(void)
{
	static const char pre[] = "/BISLPM-66301R";
	u32 i;
	for (i = 0; pre[i]; i++)
		pattern[i] = pre[i];
	pattern[i++] = kuro_on ? 'N' : menu_state == ARRANGE_MENU ? 'R' : 'A';
	pattern[i++] = '*';
	pattern[i] = 0;
	n = k = cur = top = 0;
	msg = t_load;
	st = R_LIST;
	mc_list(pattern, TABLE, MAX_LIST);
}

static void sort(void)
{
	u32 i, j;
	for (i = 0; i < n; i++)
		order[i] = (u8)i;
	for (i = 1; i < n; i++) /* newest first: the names end in YYMMDDhhmm */
		for (j = i; j > 0; j--) {
			const char *a = entry_name(j - 1), *b = entry_name(j);
			u32 c = 0;
			while (a[c] && a[c] == b[c])
				c++;
			if ((u8)a[c] >= (u8)b[c])
				break;
			{
				const u8 t = order[j - 1];
				order[j - 1] = order[j];
				order[j] = t;
			}
		}
}

static void dir_of(u32 i)
{
	const char *s = entry_name(i);
	u32 j = 0;
	while (s[j] && j < 30u) {
		dir[j] = s[j];
		j++;
	}
	dir[j] = 0;
}

static u32 pressed(void) { return GAME_CALL2(PAD_PRESSED, 0, 0) | GAME_CALL2(PAD_PRESSED, 1, 0); }

/* Starting a playback drives the menus as a player would: GAME START (row 0) confirmed, and in Arcade's NORMAL /
 * HARDER / EXTENDED submenu (state 3) the recorded choice confirmed; the game start reads that press for the side
 * (player 1). KURO's GAME START goes straight to the game (scripts/build_ee_hooks.py, 0x001CAAE8). */
static void start_step(void)
{
	if (EE_RAM(u32, FRONT_STATE) == menu_state)
		EE_RAM(u32, MENU_ROW) = 0;
	else if (EE_RAM(u32, FRONT_STATE) == 3u)
		EE_RAM(u32, MENU_ROW) = rpl_play_difficulty() < 3u ? rpl_play_difficulty() : 0;
	else
		return;
	if (++wait % 8u == 0u) /* a press every 8 frames until the game starts */
		inject = 0x10u;
}

/* per frame (kuro_frame): menu tables, the REPLAY row, and the list's work */
void rm_frame(void)
{
	sync_tables();
	if (EE_RAM(u32, MAIN_STATE) != 9u) {
		if (st == R_START)
			back_to_menu = menu_state;
		st = R_OFF;
		inject = 0;
		return;
	}
	if (back_to_menu && EE_RAM(u32, FRONT_STATE) == 1u) {
		/* the playback ended (RETURN MENU leads to Mode Select, state 1): this mode's menu instead, cursor on
		 * REPLAY; before kuro_frame's Mode Select check, so NOIR stays on */
		EE_RAM(u32, FRONT_STATE) = back_to_menu;
		back_to_menu = 0;
		EE_RAM(u32, FRONT_ROW) = 3u;
		EE_RAM(u32, MENU_ROW) = 3u;
		EE_RAM(u32, FRONT_ANIM) = 0;
	}
	if (st == R_OFF) {
		const u32 fs = EE_RAM(u32, FRONT_STATE);
		if ((fs == 2u || fs == ARRANGE_MENU) && EE_RAM(u32, MENU_ROW) == 3u && (pressed() & 0x10u)) {
			menu_state = fs;
			GAME_CALL2(0x001370E0u, 95, 36);
			open_list();
		}
		return;
	}
	mc_tick();
	switch (st) {
	case R_LIST:
		if (mc_busy())
			return;
		if (!mc_done()) {
			msg = (mc_error() & 0xFFFF0000) == 0x10000 ? t_card : t_fail; /* the card check failed: no card */
			st = R_MSG;
			return;
		}
		n = mc_loaded() < MAX_LIST ? mc_loaded() : MAX_LIST;
		if (!n) {
			msg = t_none;
			st = R_MSG;
			return;
		}
		sort();
		k = 0;
		st = R_HEADS;
		return;
	case R_HEADS:
		if (mc_busy())
			return;
		if (k < n) { /* each file's header: stage and score */
			dir_of(k);
			mc_load(dir, "REPLAY.DAT", HEADS + 16u * order[k], 64u);
			k++;
			return;
		}
		st = R_SHOW;
		return;
	case R_SHOW: {
		const u32 p = pressed(), b = p | GAME_CALL2(PAD_REPEAT, 0, 0); /* moves repeat; choices need a new press */
		if (b & 0x01u && cur)
			cur--;
		if (b & 0x02u && cur + 1u < n)
			cur++;
		if (cur < top)
			top = cur;
		if (cur >= top + SHOWN)
			top = cur + 1u - SHOWN;
		if (b & 0x03u)
			GAME_CALL2(0x001370E0u, 99, 28);
		if (p & 0x20u) {
			GAME_CALL2(0x001370E0u, 76, 40);
			st = R_OFF;
		} else if (p & 0x10u) {
			dir_of(cur);
			mc_load(dir, "REPLAY.DAT", rpl_buffer(), rpl_buffer_max());
			msg = t_load;
			st = R_LOAD;
		}
		return;
	}
	case R_LOAD:
		if (mc_busy())
			return;
		if (mc_done() && rpl_play_loaded(mc_loaded())) {
			st = R_START;
			wait = 0;
		} else {
			msg = t_fail;
			st = R_MSG;
			wait = 0;
		}
		return;
	case R_START:
		start_step();
		if (wait > 600u) /* the menus did not start the game: give up (the settings are restored at the next game end) */
			st = R_OFF;
		return;
	case R_MSG:
		if (++wait > 20u && (pressed() & 0x30u)) {
			st = R_OFF;
			wait = 0;
		}
		return;
	default:
		return;
	}
}

/* frontend 0x001CA294 (`jal 0x00112670`, the frame's flush): the list over the menu, then the flush */
void rm_flush(u32 a0, u32 a1)
{
	if (st != R_OFF && st != R_START) {
		u32 i, y = 152;
		((void (*)(u32, u32, u32, u32, u32))PANEL)(120, 136, 400, 176, 0x00808080u);
		((void (*)(u32, const u8 *, u32, u32, u32, u32))TEXT)(2, t_head, 136, y, 0x00808080u, 0);
		y += 32;
		if (st == R_SHOW) {
			for (i = 0; i < SHOWN && top + i < n; i++) {
				make_line(line[i], top + i);
				((void (*)(u32, const u8 *, u32, u32, u32, u32))TEXT)(2, line[i], 152, y + 16u * i,
										  top + i == cur ? 0x00808080u : 0x00404040u, 0);
			}
		} else {
			((void (*)(u32, const u8 *, u32, u32, u32, u32))TEXT)(2, msg, 136, y, 0x00808080u, 0);
		}
	}
	GAME_CALL2(0x00112670u, a0, a1);
}

/* the menu's pad reads (0x001C9438-0x001C9464): nothing while the list is open */
u32 rm_pad_repeat(u32 port) { return st != R_OFF ? 0u : GAME_CALL2(PAD_REPEAT, port, 0); }
u32 rm_pad_pressed(u32 port)
{
	if (st == R_START) {
		const u32 v = port == 0u ? inject : 0u;
		if (port == 0u)
			inject = 0;
		return v;
	}
	return st != R_OFF ? 0u : GAME_CALL2(PAD_PRESSED, port, 0);
}
