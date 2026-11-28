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

enum event_kind { RANDOM = 1, DAMAGE, GRAZE_TEST, GRAZE, RETAIL_GRAZE, POD_HIT };
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

#ifdef RP_POD_CONTACT
#define CONTACT_BASE 0x01660000u
#define CONTACT_FIRST 2000u
#define CONTACT_ROWS 768u
#define POD_BASE 0x0044C8A0u
#define TARGET_CURSOR 0x00338B98u
#define POD_SHOTS 0x0044D6C0u
#define POD_SHOT_SIZE 0x34u
#define CONTACT_CANDIDATES 8u
#define CONTACT_ENEMIES 192u

struct contact_row {
	u32 present, tick, score;
	u32 pods[3 * 0x30u / 4u], shots[48 * POD_SHOT_SIZE / 4u], enemy[ENEMY_STRIDE / 4u];
};
_Static_assert(sizeof(struct contact_row) == 2832u, "contact row layout");
_Static_assert(CONTACT_BASE + 2u * CONTACT_ROWS * sizeof(struct contact_row) <= 0x01AC0000u,
	       "pod contact trace must fit in the replay snapshot memory");
#define CONTACT ((volatile struct contact_row (*)[CONTACT_ROWS])CONTACT_BASE)
struct candidate {
	u32 flags, kind, x, y;
};
struct candidate_row {
	u32 update_plus_one;
	struct candidate enemy[CONTACT_ENEMIES];
};
#define CANDIDATES_BASE (CONTACT_BASE + 2u * CONTACT_ROWS * sizeof(struct contact_row))
#define CANDIDATES ((volatile struct candidate_row (*)[CONTACT_CANDIDATES])CANDIDATES_BASE)
_Static_assert(CANDIDATES_BASE + 2u * CONTACT_CANDIDATES * sizeof(struct candidate_row) <= 0x01AC0000u,
	       "candidate traces must fit before controller traces");

static volatile struct contact_row *contact;
static u32 contact_tick, contact_side, contact_update, candidate_count;
static u32 recorded_pods[6u * 0x30u / 4u];
static u16 recorded_target_cursor;
volatile u32 replay_contact_restore_pods; /* bit 0: pod records, bit 1: target search cursor */

static void copy_words(volatile u32 *dest, u32 source, u32 words)
{
	u32 i;
	for (i = 0; i < words; i++)
		dest[i] = EE_RAM(u32, source + 4u * i);
}

void replay_contact_step(u32 side, u32 update, u32 tick)
{
	contact = 0;
	if (tick >> 24 != 2u)
		return;
	if (update == 0)
		contact = &CONTACT[side][0];
	else if (update - CONTACT_FIRST < CONTACT_ROWS - 1u)
		contact = &CONTACT[side][update - CONTACT_FIRST + 1u];
	contact_tick = tick;
	contact_side = side;
	contact_update = update;
}

void replay_contact_clear(u32 side)
{
	u32 i;
	contact = 0;
	candidate_count = 0;
	for (i = 0; i < CONTACT_CANDIDATES; i++)
		CANDIDATES[side][i].update_plus_one = 0;
	for (i = 0; i < CONTACT_ROWS; i++)
		CONTACT[side][i].present = 0;

	if (side == 0) {
		copy_words(recorded_pods, POD_BASE, sizeof(recorded_pods) / 4u);
		recorded_target_cursor = EE_RAM(u16, TARGET_CURSOR);
	} else {
		if (replay_contact_restore_pods & 1u)
			for (i = 0; i < sizeof(recorded_pods) / 4u; i++)
				EE_RAM(u32, POD_BASE + 4u * i) = recorded_pods[i];
		if (replay_contact_restore_pods & 2u)
			EE_RAM(u16, TARGET_CURSOR) = recorded_target_cursor;
	}
}

static void sample_candidates(void)
{
	volatile struct candidate_row *row;
	u32 i;

	if (candidate_count >= CONTACT_CANDIDATES ||
	    !(EE_RAM(u32, POD_BASE) | EE_RAM(u32, POD_BASE + 0x30u) | EE_RAM(u32, POD_BASE + 0x60u)))
		return;
	row = &CANDIDATES[contact_side][candidate_count++];
	for (i = 0; i < CONTACT_ENEMIES; i++) {
		const u32 slot = ENEMY_BASE + i * ENEMY_STRIDE;
		row->enemy[i] = (struct candidate){
			EE_RAM(u32, slot), EE_RAM(u32, slot + 4u), EE_RAM(u32, slot + 0x24u), EE_RAM(u32, slot + 0x28u),
		};
	}
	row->update_plus_one = contact_update + 1u;
}

void replay_contact_sample(void)
{
	volatile struct contact_row *row = contact;
	if (!row)
		return;
	sample_candidates();
	row->tick = contact_tick;
	row->score = EE_RAM(u32, PS2_PLAYER_BASE + PS2_PLAYER_SCORE);
	copy_words(row->pods, POD_BASE, sizeof(row->pods) / 4u);
	copy_words(row->shots, POD_SHOTS, sizeof(row->shots) / 4u);
	copy_words(row->enemy, ENEMY_BASE + 3u * ENEMY_STRIDE, sizeof(row->enemy) / 4u);
	row->present = 1u | ((u32)EE_RAM(u16, TARGET_CURSOR) << 16);
}

void replay_contact_hit(u32 shot, u32 enemy)
{
	if (current)
		emit(POD_HIT, (shot - POD_SHOTS) / POD_SHOT_SIZE, (enemy - ENEMY_BASE) / ENEMY_STRIDE,
		     EE_RAM(u32, shot + 4u));
}
#endif
