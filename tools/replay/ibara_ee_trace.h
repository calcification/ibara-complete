#ifndef IBARA_EE_TRACE_H
#define IBARA_EE_TRACE_H

#include <stdint.h>

#define BLOOM_TRACE_CAPACITY 2048u

struct bloom_trace_row {
    uint32_t observed_input;
    int32_t player_x, player_y;
    uint32_t score, rank, hostile_bullets, enemies, enemy_type, enemy_state, enemy_hp;
    uint32_t stage, bomb_stock, lives, xtc, player_can_be_hit, invincibility_timer;
};

struct bloom_trace {
    uint32_t magic, frames;
    struct bloom_trace_row samples[BLOOM_TRACE_CAPACITY];
};

void bloom_trace_reset(volatile struct bloom_trace *trace);
void bloom_trace_sample(volatile struct bloom_trace *trace, uint32_t observed_input, uint32_t xtc_displayed);
void bloom_trace_stage1_sample(volatile struct bloom_trace *trace, uint32_t observed_input, uint32_t xtc_displayed);

#endif
