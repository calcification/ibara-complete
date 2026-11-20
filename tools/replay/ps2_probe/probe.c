/* Original PS2 homebrew for validating an emulator's delivery of a movie. */
#include <stdint.h>

#include <debug.h>
#include <graph.h>
#include <iopcontrol.h>
#include <libpad.h>
#include <loadfile.h>
#include <sifrpc.h>

#define CAPACITY 2048

struct sample {
    uint32_t input;
    int32_t x;
    int32_t y;
    uint32_t shots;
};

struct trace {
    uint32_t magic;
    uint32_t frames;
    struct sample rows[CAPACITY];
};

static volatile struct trace *const trace = (struct trace *)0x01F00000;
static unsigned char pad_buffer[256] __attribute__((aligned(64)));

static uint32_t control_mask(unsigned pressed)
{
    const unsigned map[] = {
        PAD_UP, PAD_DOWN, PAD_LEFT, PAD_RIGHT, PAD_CROSS, PAD_CIRCLE,
        PAD_SQUARE, PAD_TRIANGLE, PAD_START, 0, PAD_SELECT,
    };
    uint32_t result = 0;
    for (unsigned i = 0; i < sizeof(map) / sizeof(*map); ++i)
        result |= (pressed & map[i] ? 1u : 0u) << i;
    return result;
}

int main(void)
{
    init_scr();
    sceSifInitRpc(0);
    while (!SifIopReset(NULL, 0))
        graph_wait_vsync();
    while (!SifIopSync())
        graph_wait_vsync();
    sceSifInitRpc(0);
    if (SifLoadModule("rom0:SIO2MAN", 0, NULL) < 0 ||
        SifLoadModule("rom0:PADMAN", 0, NULL) < 0 ||
        padInit(0) < 0 || !padPortOpen(0, 0, pad_buffer)) {
        scr_printf("Controller setup failed.\n");
        return 1;
    }
    trace->magic = 0x46524231;
    trace->frames = 0;
    scr_printf("Replay probe: waiting for first button.\n");
    int32_t x = 0, y = 0;
    uint32_t shots = 0;
    for (;;) {
        graph_wait_vsync();
        struct padButtonStatus buttons;
        int status = padGetState(0, 0);
        if ((status != PAD_STATE_STABLE && status != PAD_STATE_FINDCTP1) ||
            !padRead(0, 0, &buttons))
            continue;
        uint32_t mask = control_mask(buttons.btns ^ 0xFFFFu);
        if ((!trace->frames && !mask) || trace->frames >= CAPACITY)
            continue;
        x += !!(mask & 8) - !!(mask & 4);
        y += !!(mask & 2) - !!(mask & 1);
        shots += !!(mask & 16);
        unsigned index = trace->frames;
        trace->rows[index] = (struct sample){mask, x, y, shots};
        trace->frames = index + 1;
    }
}
