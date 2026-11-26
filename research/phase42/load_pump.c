/* Load pump (research/phase42). The game's load queue service 0x0010D520 is called once per frame (0x00113398,
 * 0x00117058) and does one step per call: issue the next archive read, or notice the read in flight has finished and
 * run its callback. Both CPUs are mostly idle while loading (research/phase18), so each entry waits up to two frames
 * for the frame loop. load_pump runs after the retail call (stub) and calls the service again while there is work,
 * for up to LOAD_PUMP_US microseconds of the frame. Every call also logs scene changes with a timestamp. */
#include "ibara_ps2.h"

#ifndef LOAD_PUMP_US
#define LOAD_PUMP_US 0u
#endif
#define EE_HZ 294912000u
#define BUSY      0x00339D90u /* read in flight */
#define Q_HEAD    0x0033AF20u /* load queue ring: head, tail (s16) */
#define REL_HEAD  0x0033E350u /* release ring */
#define SCENE     0x00338E9Cu
#define TRANS     0x00338F40u

struct lp_event { u32 ms, scene, trans, pumped; };
struct lp_log { u32 magic, n, budget_us, total_ms; u32 busy_frames, idle_frames, entries, pad; struct lp_event ev[60]; };
struct lp_log lp_log;
static u32 lp_last_count, lp_ms_frac, lp_pumped;
static u8 lp_scene = 0xFF;
static u32 lp_trans = 0xFFFFFFFFu;

static inline u32 cp0_count(void)
{
	u32 c;
	__asm__ volatile("mfc0 %0, $9" : "=r"(c));
	return c;
}

static u32 lp_work(void)
{
	return EE_RAM(u32, BUSY) || EE_RAM(s16, Q_HEAD) != EE_RAM(s16, Q_HEAD + 2u) ||
	       EE_RAM(s16, REL_HEAD) != EE_RAM(s16, REL_HEAD + 2u);
}

void load_pump(void)
{
	const u32 start = cp0_count();
	u32 calls = 0;
#ifdef LOAD_PUMP_NOSPIN
	/* never wait on a read in flight: only issue queued entries the frame's call left idle */
	while (!EE_RAM(u32, BUSY) && EE_RAM(s16, Q_HEAD) != EE_RAM(s16, Q_HEAD + 2u) && calls < 16u) {
		GAME_CALL0(0x0010D520u);
		calls++;
	}
#endif
	if (LOAD_PUMP_US) {
		const u32 budget = LOAD_PUMP_US * (EE_HZ / 1000000u);
		while (lp_work() && cp0_count() - start < budget && calls < 100000u) {
			GAME_CALL0(0x0010D520u);
			calls++;
		}
	}
	lp_pumped += calls;
	if (EE_RAM(u8, SCENE) == 2u && EE_RAM(u32, TRANS) == 1u) { /* stage-1 loading window */
		static u32 was_busy;
		const u32 b = EE_RAM(u32, BUSY) != 0;
		if (b)
			lp_log.busy_frames++;
		else
			lp_log.idle_frames++;
		if (b && !was_busy)
			lp_log.entries++;
		was_busy = b;
	}
	/* clock and scene log */
	{
		const u32 now = cp0_count();
		u32 d = now - lp_last_count;
		lp_last_count = now;
		if (lp_log.magic != 0x31504D50u) { /* "PMP1" */
			lp_log.magic = 0x31504D50u;
			lp_log.n = 0;
			lp_log.total_ms = 0;
			d = 0;
		}
		if (d > EE_HZ)
			d = 0; /* first call / long gap */
		lp_ms_frac += d;
		lp_log.total_ms += lp_ms_frac / (EE_HZ / 1000u);
		lp_ms_frac %= EE_HZ / 1000u;
		lp_log.budget_us = LOAD_PUMP_US;
	}
	if ((EE_RAM(u8, SCENE) != lp_scene || EE_RAM(u32, TRANS) != lp_trans) && lp_log.n < 60u) {
		struct lp_event *e = &lp_log.ev[lp_log.n++];
		lp_scene = EE_RAM(u8, SCENE);
		lp_trans = EE_RAM(u32, TRANS);
		e->ms = lp_log.total_ms;
		e->scene = lp_scene;
		e->trans = lp_trans;
		e->pumped = lp_pumped;
	}
}
