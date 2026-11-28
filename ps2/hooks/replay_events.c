/* Ordered Noir Stage 1 events. Added only by build_trace.py. */
#include "ibara_ps2.h"

#ifndef RP_EVENT_START
#define RP_EVENT_START 1000u
#endif
#define WINDOW_COUNT 128u
#define EVENTS_MAX 8064u
#define EVENTS_BASE 0x01EC0000u
#define ENEMY_BASE 0x0045A840u
#define ENEMY_STRIDE 0xB4u

enum event_kind { RANDOM = 1, DAMAGE, GRAZE_TEST, GRAZE, RETAIL_GRAZE };
struct event { u32 kind, a, b, c; };
struct event_row { u32 stage_tick, first, count, dropped; };
struct event_trace {
	struct event_row row[WINDOW_COUNT];
	struct event event[EVENTS_MAX];
};
_Static_assert(sizeof(struct event_row) == 16u, "late trace row layout");
_Static_assert(sizeof(struct event_trace) == 0x20000u, "late trace layout");
_Static_assert(EVENTS_BASE + 2u * sizeof(struct event_trace) <= 0x01F00000u,
	       "late trace must fit between replay input and hooks");
#define EVENTS ((volatile struct event_trace *)EVENTS_BASE)

const volatile u32 replay_late_window_start = RP_EVENT_START;

static volatile struct event_row *current;
static volatile struct event *events;
static u32 used, between_updates;

void replay_late_begin(u32 side, u32 update, u32 tick)
{
	const u32 offset = update - replay_late_window_start;
	current = 0;
	between_updates = 0;
	if (tick >> 24 != 2u || offset >= WINDOW_COUNT)
		return;
	events = EVENTS[side].event;
	current = &EVENTS[side].row[offset];
	current->first = used;
	current->count = current->dropped = 0;
	current->stage_tick = tick;
}

void replay_late_end(void)
{
	between_updates = 1;
}

void replay_late_end_game(void)
{
	current = 0;
}

void replay_late_clear(u32 side)
{
	u32 i;
	current = 0;
	used = 0;
	for (i = 0; i < WINDOW_COUNT; i++)
		EVENTS[side].row[i].stage_tick = 0;
}

static void emit(u32 kind, u32 a, u32 b, u32 c)
{
	volatile struct event_row *row = current;

	if (!row)
		return;
	if (used == EVENTS_MAX) {
		row->dropped++;
		return;
	}
	events[used++] = (struct event){kind | (between_updates << 16), a, b, c};
	row->count++;
}

void replay_late_random(u32 caller, u32 limit)
{
	if (current)
		emit(RANDOM, caller - 8u, limit, EE_RAM(u32, 0x00337D08u));
}

u32 replay_late_damage_before(u32 enemy)
{
	if (current && enemy - ENEMY_BASE < 192u * ENEMY_STRIDE)
		return 0x10000u | EE_RAM(u16, enemy + 0x3Cu);
	return 0;
}

void replay_late_damage_after(u32 enemy, u32 caller, u32 amount, u32 sample, u32 result)
{
	u32 before, after, slot;

	if (!sample)
		return;
	before = sample & 0xFFFFu;
	after = EE_RAM(u16, enemy + 0x3Cu);
	if (before == after && !result)
		return;
	slot = (enemy - ENEMY_BASE) / ENEMY_STRIDE;
	emit(DAMAGE, caller - 8u, slot | ((amount & 0xFFFFu) << 8) | ((result != 0) << 24),
	     before | (after << 16));
}

void replay_late_graze_test(u32 side, u32 held, u32 pods, u32 flags)
{
	emit(GRAZE_TEST, side | (held << 8) | (pods << 16), flags, 0);
}

void replay_late_graze(u32 slot, s32 dx, s32 dy, u32 half_width, u32 half_height)
{
	emit(GRAZE, slot | (half_width << 8) | (half_height << 16), (u32)dx, (u32)dy);
}

void replay_late_retail_graze(u32 caller, u32 object, u32 side, u32 score)
{
	const u32 bullet = caller == 0x0012A934u;
	const u32 slot = bullet ? (object - PS2_BULLETS_BASE) / PS2_BULLET_STRIDE :
				 (object - ENEMY_BASE) / ENEMY_STRIDE;

	emit(RETAIL_GRAZE, caller - 8u, side | (slot << 8), score);
}
