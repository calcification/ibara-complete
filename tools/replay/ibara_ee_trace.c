/* Optional test observer for the PS2 build. Call after the same game update
 * on each frame, from an opt-in test hook. This does not change gameplay RAM. */
#include "ibara_ee_trace.h"

#define TRACE_MAGIC 0x46524232u
#define PLAYER 0x0044C380u
#define ENEMIES 0x0045A840u
#define BULLETS 0x00462F40u
#define STAGE_COUNTER 0x00338E9Cu
#define PLAYER_CAN_BE_HIT 0x04000000u
#define READ32(addr) (*(const volatile uint32_t *)(uintptr_t)(addr))
#define READ16(addr) (*(const volatile uint16_t *)(uintptr_t)(addr))
#define READ8(addr) (*(const volatile uint8_t *)(uintptr_t)(addr))

_Static_assert(sizeof(struct bloom_trace_row) == 64, "trace row must use 16 consecutive words");

/* Trace storage must be reserved in writable EE RAM by the test build. */
void bloom_trace_reset(volatile struct bloom_trace *trace)
{
    trace->frames = 0;
    trace->magic = TRACE_MAGIC;
}

void bloom_trace_sample(volatile struct bloom_trace *trace, uint32_t observed_input, uint32_t xtc_displayed)
{
    uint32_t frame = trace->frames;
    if (trace->magic != TRACE_MAGIC || frame >= BLOOM_TRACE_CAPACITY)
        return;

    struct bloom_trace_row row = {
        .observed_input = observed_input,
        .player_x = (int32_t)READ32(PLAYER + 0x10) >> 16,
        .player_y = (int32_t)READ32(PLAYER + 0x14) >> 16,
        .score = READ32(PLAYER + 0x280),
        .rank = READ32(0x00338EB4u) & 0x00FFFFFFu,
        .stage = READ32(STAGE_COUNTER) & 0xFFu,
        .bomb_stock = READ8(PLAYER + 0x25Du),
        .lives = READ8(PLAYER + 0x25Au),
        .xtc = xtc_displayed,
        .player_can_be_hit = !!(READ32(PLAYER) & PLAYER_CAN_BE_HIT),
        .invincibility_timer = READ8(PLAYER + 0x27Au),
        .enemy_type = UINT32_MAX,
        .enemy_state = UINT32_MAX,
        .enemy_hp = UINT32_MAX,
    };
    for (unsigned i = 0; i < 192; ++i) {
        uint32_t slot = ENEMIES + i * 0xB4u;
        if (READ32(slot) & 0x80000000u) {
            if (!row.enemies) {
                row.enemy_type = READ32(slot + 4);
                row.enemy_state = READ32(slot + 8);
                row.enemy_hp = READ16(slot + 0x3C);
            }
            ++row.enemies;
        }
    }
    for (unsigned i = 0; i < 256; ++i) {
        uint32_t slot = BULLETS + i * 0x54u;
        if ((READ32(slot) & 0x10004000u) == 0x10000000u)
            ++row.hostile_bullets;
    }
    trace->samples[frame] = row;
    trace->frames = frame + 1;
}

void bloom_trace_stage1_sample(volatile struct bloom_trace *trace, uint32_t observed_input,
                               uint32_t xtc_displayed)
{
    if ((READ32(STAGE_COUNTER) & 0xFFu) != 2)
        return;
    if (trace->magic != TRACE_MAGIC) {
        if (!(READ32(PLAYER) & PLAYER_CAN_BE_HIT))
            return;
        bloom_trace_reset(trace);
    }
    bloom_trace_sample(trace, observed_input, xtc_displayed);
}
