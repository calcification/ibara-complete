/* Replay experiment (research/phase44; test builds only for now).
 *
 * Inputs are recorded and replayed per game update, not per pad read. The retail loop polls the pad from its
 * vsync wait (0x00113390 -> 0x00112A80), so the number of polls per update depends on timing: the same game
 * polled twice per update in one run and once in another (phase 44). The update itself starts at 0x0012E5CC
 * (`jal 0x00138CD0`, the first call of the update path); game_start.c calls replay_update there (REPLAY_BUILD),
 * after its own start-of-game reset (item drop state, XTC, boss-cancel tracker):
 *   RECORD: stores both players' button words (+0x24C held, +0x24E pressed, +0x250, +0x252, +0x254) per update.
 *   PLAY:   writes the stored words back before the update runs.
 * During playback the pad reads return the recorded pad values of the next update (the shot code reads the pad
 * arrays, not only the player words), so the live pad cannot pause or steer the game.
 * A game runs while MAIN_STATE is 5 (a game) outside attract mode; recording starts at its first update (after the
 * loading and ship select screens), where the random seed, the frame counter and the enemy group counter are
 * stored / restored.
 * Checkpoints (score, rank, scene and stage tick, seed) every 10 updates up to 1000, then every 300. */
#include "ibara_ps2.h"

#define SEED     0x00337D08u /* $gp-32744 */
#define FRAMES   0x00338CDCu /* $gp-28692 */
#define GROUP_ID 0x00338E4Cu /* $gp-28324, u16 */
#define SCENE    0x00338E9Cu
#define TICK     0x00338EA0u
#define RANK     0x00338EB4u
#define ATTRACT  0x00338E7Cu
#define MAIN_STATE 0x00338B08u /* 5: a game is running (9: frontend) */
#define CP_MAX 1400u
#ifndef RP_FIRST_MODE
#define RP_FIRST_MODE 0u /* 2: ignore the first game (experiment) */
#endif
#define BTN_WORDS 5u /* +0x24C .. +0x254 */

#define PADBLK 0x00341FA0u /* 2 x 0x50: +0 current, +4 previous, +8 pressed, +0xC repeat, timers */
struct rp_upd { u32 tick, rank, frames; u16 w[2][BTN_WORDS]; u16 raw[2]; u32 blk[40]; };
static u16 rp_raw[2]; /* record: the latest pad values */ /* tick = scene << 24 | stage tick, checked on playback */
#define RP_LOG ((struct rp_upd *)0x01B00000u) /* experiment: RAM unused in a game (0x01650000-0x01ED0000) */
#define RP_LOG_MAX 20000u
struct rp_cp { u32 upd, score, rank, stage_tick, seed, x, y, bombs; };
struct rp_state {
	u32 magic, mode, n_upd, play_upd, overflow, cp_n[2], tick_miss, play_done;
	u32 seed0, frames0, group0[4], first_miss; /* group0: enemy group counter and spawn serial (0x00338E4C-0x00338E53) */
	u32 rank0[4]; /* 0x00338EAC-0x00338EBB: rank state set at game init (0x00338EB8 += rand(2) before the first update) */
	u32 players0[2u * PS2_PLAYER_STRIDE / 4u]; /* both player records at the first update (ship, bomb, timers) */
} rp;
#define RP_CP ((struct rp_cp (*)[CP_MAX])0x01FC0000u) /* experiment */

#ifdef RP_LATE_TRACE
_Static_assert(0x01B00000u + RP_LOG_MAX * sizeof(struct rp_upd) <= 0x01EC0000u,
	       "replay input must fit before the late event trace");
void replay_late_begin(u32 side, u32 update, u32 tick);
void replay_late_clear(u32 side);
void replay_late_end_game(void);
#endif

static u8 rp_active, rp_started; /* in a game; its first update has run */

#ifdef RP_CONTROLLER_TRACE
#define RP_TRACE_FRAMES 1200u

struct controller_trace {
	u32 scroll, step, cursor, wait, position, animation, kind, active;
	u32 calls, result, spawn_tick, spawn_scroll, spawn_seed, spawn_cursor;
	u32 resource_checks, resources_ready, pool_checks, pool_ready;
};

/* Past the default snapshots (end 0x01AC0000); before the input log. */
#define RP_TRACE ((volatile struct controller_trace (*)[RP_TRACE_FRAMES])0x01AC0000u)
_Static_assert(2u * RP_TRACE_FRAMES * sizeof(struct controller_trace) <= 0x40000u,
	       "controller traces must fit before the input log");

static void trace_controller(u32 side, u32 update)
{
	const u32 slot = 0x0045A840u + 3u * 0xB4u;
	volatile struct controller_trace *row;

	if (update >= RP_TRACE_FRAMES)
		return;
	row = &RP_TRACE[side][update];
	*row = (struct controller_trace){0};
	row->scroll = EE_RAM(u32, 0x00338DD0u);
	row->step = EE_RAM(u32, 0x00338DD8u);
	row->cursor = EE_RAM(u32, 0x00338E00u);
	row->wait = EE_RAM(u32, 0x00338DFCu);
	row->active = EE_RAM(u32, slot) >> 31;
	if (row->active) {
		row->kind = EE_RAM(u32, slot + 4);
		if (row->kind == 76u) {
			row->position = EE_RAM(u32, slot + 0x24u);
			row->animation = EE_RAM(u16, slot + 0x98u);
		}
	}
}

static volatile struct controller_trace *controller_event(void)
{
	const u32 side = rp.mode;
	const u32 next = side == 0 ? rp.n_upd : rp.play_upd;

	if (!rp_started || side >= 2 || next == 0 || next > RP_TRACE_FRAMES ||
	    (side == 1 && next > rp.n_upd))
		return 0;
	return &RP_TRACE[side][next - 1];
}

u32 replay_controller_create(void)
{
	volatile struct controller_trace *row = controller_event();
	u32 result;

	if (row) {
		row->calls++;
		row->spawn_tick = EE_RAM(u32, TICK);
		row->spawn_scroll = EE_RAM(u32, 0x00338DD0u);
		row->spawn_seed = EE_RAM(u32, SEED);
		row->spawn_cursor = EE_RAM(u32, 0x00338E00u);
	}
	result = GAME_CALL0(0x00163350u);
	if (row)
		row->result = result;
	return result;
}

/* Positive-control build only: make the first successful playback resource
 * check retry once, after the native check has done its normal work. */
#ifdef RP_CONTROLLER_ONE_UPDATE
static u32 controller_delayed;
#endif

#ifdef RP_CONTROLLER_SYNC
/* Diagnostic only. Shadow the recorded type-76 factory outcome in Stage 1.
 * When playback is late, use the normal render-only path so CD reads and GS
 * uploads continue while the input log and stage interpreter stay put. */
#define CONTROLLER_HOLD_MAX 120u
struct controller_sync_stats {
	u32 forced_record_retries, early_blocks, withheld_checks;
	u32 render_holds, timeouts, cursor_misses;
};
volatile struct controller_sync_stats replay_controller_sync_stats;

u32 replay_controller_may_update(void)
{
	const volatile struct controller_trace *recorded;

	if (!rp_started || rp.mode != 1u || EE_RAM(u8, SCENE) != 2u ||
	    rp.play_upd >= rp.n_upd || rp.play_upd >= RP_TRACE_FRAMES)
		return 1u;
	recorded = &RP_TRACE[0][rp.play_upd];
	if (!recorded->result)
		return 1u;
	if (recorded->calls != 1u || recorded->cursor != EE_RAM(u32, 0x00338E00u)) {
		replay_controller_sync_stats.cursor_misses++;
		return 1u;
	}
	if (GAME_CALL2(0x00135D70u, 76u, 0xFFFF8000u))
		return 1u;
	if (replay_controller_sync_stats.render_holds >= CONTROLLER_HOLD_MAX) {
		replay_controller_sync_stats.timeouts++;
		return 1u;
	}
	replay_controller_sync_stats.render_holds++;
	return 0u;
}

#endif

u32 replay_controller_resources(u32 kind, u32 flags)
{
	volatile struct controller_trace *row = controller_event();
	u32 result;

#ifdef RP_CONTROLLER_SYNC
	const volatile struct controller_trace *recorded = 0;
	const u32 sync = row && kind == 76u && EE_RAM(u8, SCENE) == 2u;

	if (sync && rp.mode == 1u) {
		recorded = &RP_TRACE[0][rp.play_upd - 1u];
		if (recorded->calls != 1u || recorded->spawn_cursor != row->spawn_cursor)
			recorded = 0;
	}
#ifdef RP_CONTROLLER_WITHHOLD_LOAD
	if (recorded && !recorded->result) {
		replay_controller_sync_stats.withheld_checks++;
		return 0;
	}
#endif
#endif
	result = GAME_CALL2(0x00135D70u, kind, flags);
	if (row) {
		row->resource_checks++;
		row->resources_ready += result != 0;
	}
#ifdef RP_CONTROLLER_SYNC
#ifdef RP_CONTROLLER_RECORD_RETRIES
	if (sync && rp.mode == 0u && result &&
	    replay_controller_sync_stats.forced_record_retries < RP_CONTROLLER_RECORD_RETRIES) {
		replay_controller_sync_stats.forced_record_retries++;
		return 0;
	}
#endif
	if (recorded && !recorded->result && result) {
		replay_controller_sync_stats.early_blocks++;
		return 0;
	}
#endif
#ifdef RP_CONTROLLER_ONE_UPDATE
	if (row && rp.mode == 1u && kind == 76u && result && !controller_delayed) {
		controller_delayed = 1u;
		return 0;
	}
#endif
	return result;
}

u32 replay_controller_slots(u32 count)
{
	const u32 result = ((u32 (*)(u32))0x0012D280u)(count);
	volatile struct controller_trace *row = controller_event();

	if (row) {
		row->pool_checks++;
		row->pool_ready += result != 0;
	}
	return result;
}
#endif

static void checkpoint(u32 which, u32 upd)
{
	struct rp_cp *c;
	if ((upd >= 1200u && upd % 300u) || rp.cp_n[which] >= CP_MAX)
		return;
	c = &RP_CP[which][rp.cp_n[which]++];
	c->upd = upd;
	c->score = EE_RAM(u32, PS2_PLAYER_BASE + PS2_PLAYER_SCORE);
	c->rank = EE_RAM(u32, RANK);
	c->stage_tick = (u32)EE_RAM(u8, SCENE) << 24 | (EE_RAM(u32, TICK) & 0xFFFFFFu);
	c->seed = EE_RAM(u32, SEED);
	c->x = EE_RAM(u32, PS2_PLAYER_BASE + PS2_PLAYER_X);
	c->y = EE_RAM(u32, PS2_PLAYER_BASE + PS2_PLAYER_Y);
	c->bombs = EE_RAM(u8, PS2_PLAYER_BASE + PS2_PLAYER_BOMBS);
}

/* Objects the game spawns into a slot keep fields it does not initialise (left over from the previous game), so
 * every inactive slot is cleared at the first update of a recorded or replayed game. */
static void clear_pool(u32 base, u32 stride, u32 count, u32 all)
{
	u32 i, w;
	for (i = 0; i < count; i++, base += stride)
		if (all || !(EE_RAM(u32, base) & 0x80000000u))
			for (w = 0; w < stride; w += 4u)
				EE_RAM(u32, base + w) = 0;
}

#ifdef RP_REGIONS /* experiment: copy these regions from the recording's first update into the playback's */
static const u32 rp_regions[][2] = {RP_REGIONS};
static void regions(u32 restore)
{
	u32 *buf = (u32 *)0x01A80000u, r, a;
	for (r = 0; r < sizeof(rp_regions) / sizeof(rp_regions[0]); r++)
		for (a = rp_regions[r][0]; a < rp_regions[r][1]; a += 4u, buf++) {
			if (restore)
				EE_RAM(u32, a) = *buf;
			else
				*buf = EE_RAM(u32, a);
		}
}
#endif

static void game_start(void)
{
	u32 i;
	rp_started = 1;
	if (rp.mode == 2u)
		return;
#ifdef RP_LATE_TRACE
	replay_late_clear(rp.mode);
#endif
	/* no shot, item or bullet exists at a stage's first update, but items can survive RETURN MENU */
	clear_pool(PS2_SHOTS_BASE, PS2_SHOT_STRIDE, 256u, 1u);
	clear_pool(PS2_ITEMS_BASE, 0x58u, 256u, 1u);
	clear_pool(0x0045A840u, 0xB4u, 192u, 0u);
	clear_pool(PS2_BULLETS_BASE, PS2_BULLET_STRIDE, PS2_BULLET_COUNT, 1u);
	clear_pool(0x00468340u, 0x3Cu, 532u, 0u); /* the pool after the bullets (0x3C records, effects) */
#ifdef RP_CONTROLLER_SYNC
	replay_controller_sync_stats.early_blocks = 0;
	replay_controller_sync_stats.withheld_checks = 0;
	replay_controller_sync_stats.render_holds = 0;
	replay_controller_sync_stats.timeouts = 0;
	replay_controller_sync_stats.cursor_misses = 0;
#endif
	if (rp.mode == 0) {
#ifdef RP_CONTROLLER_SYNC
		replay_controller_sync_stats.forced_record_retries = 0;
#endif
		rp.seed0 = EE_RAM(u32, SEED);
		rp.frames0 = EE_RAM(u32, FRAMES);
		for (i = 0; i < 2u; i++)
			rp.group0[i] = EE_RAM(u32, GROUP_ID + 4u * i);
		for (i = 0; i < 2u * PS2_PLAYER_STRIDE / 4u; i++)
			rp.players0[i] = EE_RAM(u32, PS2_PLAYER_BASE + 4u * i);
		for (i = 0; i < 4u; i++)
			rp.rank0[i] = EE_RAM(u32, 0x00338EACu + 4u * i);
#ifdef RP_REGIONS
		regions(0);
#endif
		rp.n_upd = rp.overflow = rp.cp_n[0] = 0;
	} else {
		EE_RAM(u32, SEED) = rp.seed0;
		EE_RAM(u32, FRAMES) = rp.frames0;
		for (i = 0; i < 2u; i++)
			EE_RAM(u32, GROUP_ID + 4u * i) = rp.group0[i];
		for (i = 0; i < 2u * PS2_PLAYER_STRIDE / 4u; i++)
			EE_RAM(u32, PS2_PLAYER_BASE + 4u * i) = rp.players0[i];
		for (i = 0; i < 4u; i++)
			EE_RAM(u32, 0x00338EACu + 4u * i) = rp.rank0[i];
#ifdef RP_REGIONS
		regions(1);
#endif
		rp.play_upd = rp.play_done = rp.cp_n[1] = rp.tick_miss = 0;
		rp.first_miss = 0xFFFFFFFFu;
	}
}

static void game_end(void)
{
#ifdef RP_LATE_TRACE
	replay_late_end_game();
#endif
	rp_active = rp_started = 0;
	if (rp.mode == 2u)
		rp.mode = 0;
	else if (rp.mode == 0)
		rp.mode = 1;
	else
		rp.play_done = 1;
}

/* Called for each pad read (both ports): tracks game start / end; masks the live pad during playback. */
u32 replay_pad(u32 port, u32 buttons)
{
	if (rp.magic != 0x33504552u) { /* "REP3" */
		rp.magic = 0x33504552u;
		rp.mode = RP_FIRST_MODE;
		rp.n_upd = rp.overflow = rp.cp_n[0] = rp.cp_n[1] = 0;
	}
	if (port == 0u) {
		const u32 in_game = EE_RAM(u32, MAIN_STATE) == 5u && !EE_RAM(u8, ATTRACT);
		if (rp_active && !in_game)
			game_end();
		if (!rp_active && in_game)
			rp_active = 1;
	}
	if (!rp_started || port > 1u)
		return buttons;
	if (port == 0u)
		EE_RAM(u32, FRAMES) -= 1u; /* 0x00113390 counts vsyncs; during a game it counts updates instead */
	if (rp.mode == 0u)
		rp_raw[port] = (u16)buttons;
	else if (rp.mode == 1u)
		return rp.play_upd < rp.n_upd ? RP_LOG[rp.play_upd].raw[port] : 0u; /* the inputs of the next update */
	return buttons;
}

/* Called at the start of each game update. */
#ifndef RP_SNAP_AT
#define RP_SNAP_AT 925u
#endif
#if defined(RP_SNAP_WIDE) /* 0x00280000-0x00480000 and the hook area 0x01F00000-0x01F20000 */
static void snap(u32 which, u32 n)
{
	u32 *dst = (u32 *)(0x01660000u + which * 0x00220000u);
	u32 i;
	(void)n;
	for (i = 0; i < 0x00200000u / 4u; i++)
		dst[i] = ((const u32 *)0x00280000u)[i];
	for (i = 0; i < 0x00020000u / 4u; i++)
		dst[0x00200000u / 4u + i] = ((const u32 *)0x01F00000u)[i];
}
#define SNAP_N(u) ((u) == RP_SNAP_AT)
#elif defined(RP_SNAP_LOW)
static void snap(u32 which, u32 n)
{
	u32 *dst = (u32 *)(0x01660000u + which * 0x00120000u);
	u32 i;
	(void)n;
	for (i = 0; i < 0x00100000u / 4u; i++)
		dst[i] = ((const u32 *)0x00200000u)[i];
	for (i = 0; i < 0x00020000u / 4u; i++)
		dst[0x00100000u / 4u + i] = ((const u32 *)0x01F00000u)[i];
}
#define SNAP_N(u) ((u) == RP_SNAP_AT)
#elif defined(RP_SNAP_FULL)
static void snap(u32 which, u32 n)
{
	u32 *dst = (u32 *)(0x01660000u + which * 0x00200000u);
	u32 i;
	(void)n;
	for (i = 0; i < 0x00200000u / 4u; i++)
		dst[i] = ((const u32 *)0x00300000u)[i];
}
#define SNAP_N(u) ((u) == RP_SNAP_AT)
#else
#define SNAP_SIZE 0x38000u /* 0x00338000-0x00340000 then 0x00440000-0x00470000 */
static void snap(u32 which, u32 n)
{
	u32 *dst = (u32 *)(0x01660000u + (which * 10u + n) * SNAP_SIZE);
	u32 i;
	for (i = 0; i < 0x8000u / 4u; i++)
		dst[i] = ((const u32 *)0x00338000u)[i];
	for (i = 0; i < 0x30000u / 4u; i++)
		dst[0x8000u / 4u + i] = ((const u32 *)0x00440000u)[i];
}
#define SNAP_N(u) ((u) >= RP_SNAP_AT && (u) < RP_SNAP_AT + 500u && ((u) - RP_SNAP_AT) % 50u == 0u)
#endif

void replay_update(void)
{
	const u32 tick = (u32)EE_RAM(u8, SCENE) << 24 | (EE_RAM(u32, TICK) & 0xFFFFFFu);
	u32 side, i;
	if (!rp_active)
		return;
	if (!rp_started)
		game_start(); /* the first update: after the loading and the ship select screens */
	else
		EE_RAM(u32, FRAMES) += 1u;
	if (rp.mode == 2u)
		return;
	if (rp.mode == 0) {
		if (rp.n_upd >= RP_LOG_MAX) {
			rp.overflow++;
			return;
		}
		RP_LOG[rp.n_upd].tick = tick;
		RP_LOG[rp.n_upd].rank = EE_RAM(u32, RANK); /* Arcade rank creep runs per loop pass (timing) */
		RP_LOG[rp.n_upd].frames = EE_RAM(u32, FRAMES); /* check only */
#ifdef RP_BUSY_LOG
		EE_RAM(u8, 0x01A80000u + rp.n_upd) = (u8)EE_RAM(u32, 0x00339D90u);
#endif
		RP_LOG[rp.n_upd].raw[0] = rp_raw[0];
		RP_LOG[rp.n_upd].raw[1] = rp_raw[1];
		for (i = 0; i < 40u; i++)
			RP_LOG[rp.n_upd].blk[i] = EE_RAM(u32, PADBLK + 4u * i);
		for (side = 0; side < 2; side++)
			for (i = 0; i < BTN_WORDS; i++)
				RP_LOG[rp.n_upd].w[side][i] =
					EE_RAM(u16, PS2_PLAYER_BASE + side * PS2_PLAYER_STRIDE + PS2_PLAYER_HELD + 2u * i);
#ifdef RP_CONTROLLER_TRACE
		trace_controller(0, rp.n_upd);
#endif
#ifdef RP_LATE_TRACE
		replay_late_begin(0, rp.n_upd, tick);
#endif
		if (SNAP_N(rp.n_upd))
			snap(0, (rp.n_upd - RP_SNAP_AT) / 50u);
		checkpoint(0, rp.n_upd++);
		return;
	}
	if (rp.play_upd < rp.n_upd) {
		if ((RP_LOG[rp.play_upd].tick != tick || RP_LOG[rp.play_upd].frames != EE_RAM(u32, FRAMES)) &&
		    rp.tick_miss++ == 0u)
			rp.first_miss = rp.play_upd;
		EE_RAM(u32, RANK) = RP_LOG[rp.play_upd].rank;
		for (i = 0; i < 40u; i++)
			EE_RAM(u32, PADBLK + 4u * i) = RP_LOG[rp.play_upd].blk[i];
		for (side = 0; side < 2; side++)
			for (i = 0; i < BTN_WORDS; i++)
				EE_RAM(u16, PS2_PLAYER_BASE + side * PS2_PLAYER_STRIDE + PS2_PLAYER_HELD + 2u * i) =
					RP_LOG[rp.play_upd].w[side][i];
	}
#ifdef RP_BUSY_LOG
	if (rp.play_upd < 0x10000u)
		EE_RAM(u8, 0x01A90000u + rp.play_upd) = (u8)EE_RAM(u32, 0x00339D90u);
#endif
#ifdef RP_CONTROLLER_TRACE
	trace_controller(1, rp.play_upd);
#endif
#ifdef RP_LATE_TRACE
	replay_late_begin(1, rp.play_upd, tick);
#endif
	if (SNAP_N(rp.play_upd))
		snap(1, (rp.play_upd - RP_SNAP_AT) / 50u);
	checkpoint(1, rp.play_upd++);
}

/* Replaces `jal 0x0010DDD0` at 0x00112B1C / 0x00112B28 (a0 = port, set in the delay slot): calls the original,
 * then replay_pad(port, buttons), and returns its value. Saves the callee-saved registers with 128-bit sq like
 * ps2/hooks/stub.S (our C may use them with 32-bit saves). */
__asm__(
	".set push\n.set noreorder\n.set noat\n"
	".globl replay_pad_entry\n"
	"replay_pad_entry:\n"
	"	addiu $sp,$sp,-0xC0\n"
	"	sq $ra,0x00($sp)\n"
	"	sq $s0,0x10($sp)\n"
	"	sq $s1,0x20($sp)\n"
	"	sq $s2,0x30($sp)\n"
	"	sq $s3,0x40($sp)\n"
	"	sq $s4,0x50($sp)\n"
	"	sq $s5,0x60($sp)\n"
	"	sq $s6,0x70($sp)\n"
	"	sq $s7,0x80($sp)\n"
	"	sq $fp,0x90($sp)\n"
	"	sq $gp,0xA0($sp)\n"
	"	jal 0x0010DDD0\n"
	"	sw $a0,0xB0($sp)\n"
	"	lw $a0,0xB0($sp)\n"
	"	jal replay_pad\n"
	"	move $a1,$v0\n"
	"	lq $gp,0xA0($sp)\n"
	"	lq $fp,0x90($sp)\n"
	"	lq $s7,0x80($sp)\n"
	"	lq $s6,0x70($sp)\n"
	"	lq $s5,0x60($sp)\n"
	"	lq $s4,0x50($sp)\n"
	"	lq $s3,0x40($sp)\n"
	"	lq $s2,0x30($sp)\n"
	"	lq $s1,0x20($sp)\n"
	"	lq $s0,0x10($sp)\n"
	"	lq $ra,0x00($sp)\n"
	"	jr $ra\n"
	"	addiu $sp,$sp,0xC0\n"
	".set pop\n");
