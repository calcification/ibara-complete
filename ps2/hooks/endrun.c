/* K64: at the end of a run, offer to save its replay (research/phase47).
 *
 * The main state machine (0x00113400) runs state 8 (game over / name entry, 0x0013D580) after every finished game;
 * when it returns 0 the game goes on to the logos (state 1) and the title. The call at 0x00113610 comes here: after a
 * recorded run (not attract, at least MIN_UPDATES long, checksum valid) this function keeps state 8 alive and runs
 * a prompt frame each time it is called, then returns 0.
 *
 * The prompt is the game's own memory card dialog (0x001D05C0(message, cursor), the frontend's): message 11
 * ("セーブしますか？" with はい / いいえ and the rose cursor) with its two text lines pointed at our strings while the
 * prompt is up, then 14 (saving), 15 (done) or 17 (failed). A frame is built as the game's own simple states do:
 * frame service 0x00113390, begin 0x00112500, clear 0x001125B0, 0x00112A20, the dialog, flush 0x00112670(7, 7),
 * present 0x001117D0. Buttons as the game's dialogs: left / right move, shot or bomb (0x10 / 0x20) confirm.
 * The replay goes to its own save BISLPM-66301R<YYMMDDhhmm> (mcfile.c). */
#include "ibara_ps2.h"

#define MAIN_STATE 0x00338B08u
#define ATTRACT    0x00338E7Cu
#define ARRANGE    0x00338F44u
#define PRACTICE   0x00338FA4u
#define STATE8     0x0013D580u
#define DIALOG     0x001D05C0u
#define PAD_PRESSED 0x0010DDB0u /* (port): the pad block's pressed word */
#define CLOCK      0x0010C530u /* (u8 buf[8]): [6] year - 2000, [5] month, [4] day, [2] hour, [1] minute */
#define REC_SAVE   0x002A9948u /* message 11's lines: header, blank, "セーブしますか？" */
#define REC_FAIL   0x002A9998u /* message 17's lines: header, blank, "セーブに失敗しました。" */
#define MIN_UPDATES 600u
#define ICON_BYTES (964u + 0x83A8u)

#define B_LEFT  0x04u
#define B_RIGHT 0x08u
#define B_OK    0x30u

u32 rpl_valid(void);
u32 rpl_size(void);
const u8 *rpl_data(void);
u32 rpl_offer_info(u32 *mode, u32 *stage, u32 *score);
u32 mc_save(const char *dir, const char *name, const void *src, u32 size, const u8 *title, u32 title_break);
u32 mc_busy(void);
s32 mc_error(void);
u32 mc_done(void);
void mc_tick(void);
extern u32 kuro_on;

enum { P_OFF, P_LOAD, P_ASK, P_SAVE, P_DONE, P_FAIL, P_END };
#define LOADER_BUSY 0x00339D90u
static u32 phase, cursor, wait, started_save;
static u32 old_save[2], old_fail;
static char dir[28];
static u8 title[72], line_size[40];
static const u8 line_full[] = "\x8B\xF3\x82\xAB\x97\x65\x97\xCA\x82\xAA\x91\xAB\x82\xE8\x82\xDC\x82\xB9\x82\xF1\x81\x42"; /* 空き容量が足りません。 (the dialog fits about 12 full-width characters) */

/* Shift-JIS full-width text: digits, A-Z, space */
static u8 *fw(u8 *p, const char *s)
{
	for (; *s; s++) {
		const char c = *s;
		if (c >= '0' && c <= '9') {
			*p++ = 0x82;
			*p++ = (u8)(0x4F + (c - '0'));
		} else if (c >= 'A' && c <= 'Z') {
			*p++ = 0x82;
			*p++ = (u8)(0x60 + (c - 'A'));
		} else {
			*p++ = 0x81;
			*p++ = 0x40;
		}
	}
	*p = 0;
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
	return fw(p, b + i);
}

static void two(char *p, u32 v)
{
	p[0] = (char)('0' + v / 10u % 10u);
	p[1] = (char)('0' + v % 10u);
}

static void prepare(void)
{
	static const char *const modes[] = {"ARCADE", "ARRANGE", "NOIR"};
	u8 clock[8], *p;
	u32 mode, stage, score, kb;
	const char *pre = "BISLPM-66301R";
	u32 i;
	rpl_offer_info(&mode, &stage, &score);
	/* folder BISLPM-66301R<mode letter A / R / N><YYMMDDhhmm>: each mode's REPLAY menu lists its own */
	((void (*)(u8 *))CLOCK)(clock);
	for (i = 0; pre[i]; i++)
		dir[i] = pre[i];
	dir[i++] = "ARN"[mode < 3u ? mode : 0];
	two(dir + i, clock[6]);
	two(dir + i + 2, clock[5]);
	two(dir + i + 4, clock[4]);
	two(dir + i + 6, clock[2]);
	two(dir + i + 8, clock[1]);
	dir[i + 10] = 0;
	/* browser title: "イバラ　リプレイ" / "<MODE>  ST<n>  <score>" */
	{
		static const u8 head[] = "\x83\x43\x83\x6F\x83\x89\x81\x40\x83\x8A\x83\x76\x83\x8C\x83\x43";
		for (i = 0; head[i]; i++)
			title[i] = head[i];
		p = fw(title + i, modes[mode & 3u]);
		p = fw(p, " ST");
		p = fw_num(p, stage);
		p = fw(p, " ");
		fw_num(p, score);
	}
	/* "リプレイ（ＮＮＫＢ）" above the game's own "セーブしますか？": the dialog fits about 12 full-width characters */
	kb = (rpl_size() + ICON_BYTES + 1023u) / 1024u + 3u; /* the folder's entries take a few clusters */
	p = line_size;
	*p++ = 0x83; *p++ = 0x8A; *p++ = 0x83; *p++ = 0x76; /* リプ */
	*p++ = 0x83; *p++ = 0x8C; *p++ = 0x83; *p++ = 0x43; /* レイ */
	*p++ = 0x81; *p++ = 0x69;                       /* （ */
	p = fw_num(p, kb);
	p = fw(p, "KB");
	*p++ = 0x81; *p++ = 0x6A;                       /* ） */
	*p = 0;
	/* message 11 shows our line in place of its blank one while the prompt is up */
	old_save[0] = EE_RAM(u32, REC_SAVE + 4u);
	old_save[1] = EE_RAM(u32, REC_SAVE + 8u);
	old_fail = EE_RAM(u32, REC_FAIL + 4u);
	EE_RAM(u32, REC_SAVE + 4u) = (u32)line_size;
}

static void restore(void)
{
	EE_RAM(u32, REC_SAVE + 4u) = old_save[0];
	EE_RAM(u32, REC_SAVE + 8u) = old_save[1];
	EE_RAM(u32, REC_FAIL + 4u) = old_fail;
}

static void frame(u32 message, s32 cur)
{
	GAME_CALL0(0x00113390u);
	GAME_CALL0(0x00112500u);
	((void (*)(u32))0x001125B0u)(0);
	GAME_CALL0(0x00112A20u);
	if (message != 0xFFu)
		GAME_CALL2(DIALOG, message, (u32)cur);
	GAME_CALL2(0x00112670u, 7, 7);
	GAME_CALL0(0x001117D0u);
}

static u32 pressed(void)
{
	return GAME_CALL2(PAD_PRESSED, 0, 0) | GAME_CALL2(PAD_PRESSED, 1, 0);
}

/* replaces `jal 0x0013D580` at 0x00113610: nonzero keeps state 8 */
u32 endrun_state8(void)
{
	if (phase == P_OFF) {
		/* KURO skips the retail ranking / initials state and its memory card autosave (was a KURO runtime word) */
		const u32 r = kuro_on ? 0u : GAME_CALL0(STATE8);
		if (r != 0)
			return r;
		if (EE_RAM(u8, ATTRACT) || !rpl_valid() || !rpl_offer_info(0, 0, 0))
			return 0;
		prepare();
		/* the dialog's font and panel are in resource group 1, which state 8 loads first; KURO skips state 8 */
		phase = P_ASK;
		if (kuro_on) {
			((void (*)(u32))0x00129F00u)(1);
			phase = P_LOAD;
			wait = 0;
		}
		cursor = 0;
		started_save = 0;
	}
	mc_tick();
	switch (phase) {
	case P_LOAD:
		frame(0xFFu, -1);
		wait = EE_RAM(u32, LOADER_BUSY) ? 0 : wait + 1u;
		if (wait > 4u)
			phase = P_ASK;
		break;
	case P_ASK: {
		const u32 b = pressed();
		if (b & (B_LEFT | B_RIGHT))
			cursor ^= 1u;
		frame(11, (s32)cursor);
		if (b & B_OK)
			phase = cursor == 0 ? P_SAVE : P_END;
		break;
	}
	case P_SAVE:
		frame(14, -1);
		if (!started_save) {
			started_save = mc_save(dir, "REPLAY.DAT", rpl_data(), rpl_size(), title, 16u);
		} else if (!mc_busy()) {
			if (mc_done()) {
				phase = P_DONE;
			} else {
				if ((mc_error() & 0xFFFF) == (0x10000 - 1000)) /* the space check */
					EE_RAM(u32, REC_FAIL + 4u) = (u32)line_full;
				phase = P_FAIL;
			}
			wait = 0;
		}
		break;
	case P_DONE:
	case P_FAIL:
		frame(phase == P_DONE ? 15 : 17, -1);
		if (++wait > 30u && (pressed() & B_OK || wait > 240u))
			phase = P_END;
		break;
	default:
		break;
	}
	if (phase == P_END) {
		restore();
		phase = P_OFF;
		return 0;
	}
	return 1;
}
