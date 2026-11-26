/* Opt-in Stage 1–5 damage measurement. No release profile uses this hook. */
#include "ibara_ps2.h"

#define AUDIT_BASE 0x01F60000u
#define AUDIT_MAGIC 0x31444850u /* PHD1 */
#define STAGE 0x00338E9Cu
#define TICK 0x00338EA0u
#define RNG 0x00337D08u
#define ENEMIES 0x0045A840u
#define PART_SIZE 0xB4u
#define GAUGE_STATE 0x00338B5Cu
#define GAUGE_HP 0x00338B60u
#define SEED_TICK 2000u
#define RECORDS 8000u

struct audit {
	u32 magic, requested_seed, applied_seed, seeded_tick;
	u32 count, dropped, stage, boss_type;
};

struct hp_sample {
	u32 tick, gauge_hp;
	u16 part_hp, gauge_state;
	u8 slot, kind, subtype, stage;
};

_Static_assert(sizeof(struct hp_sample) == 16, "damage audit record layout");
_Static_assert(AUDIT_BASE + sizeof(struct audit) + RECORDS * sizeof(struct hp_sample) <= 0x01F80000u,
	       "damage audit storage bounds");

static volatile struct audit *const audit = (volatile struct audit *)AUDIT_BASE;
static volatile struct hp_sample *const samples =
	(volatile struct hp_sample *)(AUDIT_BASE + sizeof(struct audit));

static void measure(u32 stage, u32 tick)
{
	unsigned i;

	if (tick & 3u)
		return;
	for (i = 0; i < 192; i++) {
		const u32 part = ENEMIES + i * PART_SIZE;
		const u32 kind = EE_RAM(u32, part + 4);
		volatile struct hp_sample *row;

		if (!(EE_RAM(u32, part) & 0x80000000u) || EE_RAM(u32, part + 8) != 0)
			continue;
		if (audit->boss_type ? kind != audit->boss_type : EE_RAM(u32, part + 0x40) < 50000u)
			continue;
		if (audit->count >= RECORDS) {
			audit->dropped++;
			return;
		}
		row = &samples[audit->count++];
		row->tick = tick;
		row->gauge_hp = EE_RAM(u32, GAUGE_HP);
		row->part_hp = EE_RAM(u16, part + 0x3C);
		row->gauge_state = (u16)EE_RAM(u32, GAUGE_STATE);
		row->slot = i;
		row->kind = kind;
		row->subtype = 0;
		row->stage = stage;
	}
}

void bl_damage_audit_players(void)
{
	static u8 was_shooting;
	const u32 stage = EE_RAM(u8, STAGE);
	const u32 tick = EE_RAM(u32, TICK);
	const u32 p1 = PS2_PLAYER_BASE;
	const u8 playing = stage >= 2u && stage <= 6u && EE_RAM(u32, p1 + PS2_PLAYER_FLAGS) != 0;

	if (playing) {
		if (audit->magic != AUDIT_MAGIC || audit->stage != stage) {
			audit->requested_seed = audit->applied_seed = audit->seeded_tick = 0;
			audit->count = audit->dropped = audit->boss_type = 0;
			audit->stage = stage;
			audit->magic = AUDIT_MAGIC;
		}
		if (tick == SEED_TICK && audit->requested_seed != 0 && audit->seeded_tick == 0) {
			audit->applied_seed = audit->requested_seed;
			audit->seeded_tick = tick;
			EE_RAM(u32, RNG) = audit->applied_seed;
		}
		EE_RAM(u16, p1 + PS2_PLAYER_HELD) = PS2_PAD_SHOT;
		EE_RAM(u16, p1 + PS2_PLAYER_PRESSED) = was_shooting ? 0 : PS2_PAD_SHOT;
		EE_RAM(u16, p1 + 0x250u) = was_shooting ? PS2_PAD_SHOT : 0;
		EE_RAM(u16, p1 + 0x252u) = 0;
		EE_RAM(u8, p1 + PS2_PLAYER_INVINCIBLE) = 240;
		EE_RAM(u8, p1 + PS2_PLAYER_LIVES + 1) = 2;
		EE_RAM(u32, PS2_RANK_INV) = 0x800000u;
	}
	was_shooting = playing;
	GAME_CALL0(0x0013AB30u);
	if (playing)
		measure(stage, tick);
}
