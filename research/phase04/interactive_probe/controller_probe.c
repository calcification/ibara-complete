#include <stdbool.h>
#include <stdio.h>

#include <debug.h>
#include <graph.h>
#include <iopcontrol.h>
#include <kernel.h>
#include <libpad.h>
#include <loadfile.h>
#include <sifrpc.h>

static unsigned char pad_buffer[256] __attribute__((aligned(64)));
static const char retail_path[] = "cdrom0:\\SLPM_663.01;1";

static void draw_screen(bool return_selected, unsigned confirmed, const char *status)
{
    scr_clear();
    scr_setXY(6, 4);
    scr_setfontcolor(0x00E6AC60);
    scr_printf("Ibara launcher test\n\n");
    scr_setfontcolor(0x00FFFFFF);
    scr_printf("      %c Check controller input\n", return_selected ? ' ' : '>');
    scr_printf("      %c Return to Ibara\n\n", return_selected ? '>' : ' ');
    scr_printf("      D-pad Up/Down selects. Circle confirms.\n\n");
    scr_printf("      %s\n", status);
    scr_printf("      Input checks: %u\n", confirmed);
}

static bool start_controller(void)
{
    // Start a fresh IOP session so the new program owns the controller DMA buffer.
    sceSifInitRpc(0);
    while (!SifIopReset(NULL, 0))
        graph_wait_vsync();
    while (!SifIopSync())
        graph_wait_vsync();
    sceSifInitRpc(0);

    if (SifLoadModule("rom0:SIO2MAN", 0, NULL) < 0 ||
        SifLoadModule("rom0:PADMAN", 0, NULL) < 0 || padInit(0) < 0)
        return false;
    return padPortOpen(0, 0, pad_buffer) != 0;
}

int main(void)
{
    bool return_selected = false;
    bool armed = false;
    bool connected = false;
    unsigned confirmed = 0;
    unsigned previous = 0;

    init_scr();
    scr_setbgcolor(0x00201812);
    draw_screen(return_selected, confirmed, "Starting Controller 1...");
    if (!start_controller()) {
        draw_screen(return_selected, confirmed, "Controller setup failed. Returning to Ibara.");
        for (int frame = 0; frame < 180; ++frame)
            graph_wait_vsync();
        LoadExecPS2(retail_path, 0, NULL);
    }

    draw_screen(return_selected, confirmed, "Waiting for Controller 1...");
    for (;;) {
        struct padButtonStatus buttons;
        int state = padGetState(0, 0);
        bool ready = (state == PAD_STATE_STABLE || state == PAD_STATE_FINDCTP1) &&
                     padRead(0, 0, &buttons) != 0;
        if (ready != connected) {
            connected = ready;
            armed = false;
            draw_screen(return_selected, confirmed,
                        ready ? "Release buttons to begin." : "Waiting for Controller 1...");
        }
        if (ready) {
            unsigned held = buttons.btns ^ 0xFFFFu;
            unsigned pressed = held & ~previous;
            previous = held;
            if (!armed && held == 0) {
                armed = true;
                draw_screen(return_selected, confirmed, "Controller 1 ready.");
            }
            if (armed && (pressed & (PAD_UP | PAD_DOWN))) {
                return_selected = !return_selected;
                draw_screen(return_selected, confirmed, "Controller 1 ready.");
            }
            if (armed && (pressed & PAD_CIRCLE)) {
                if (return_selected)
                    break;
                draw_screen(return_selected, ++confirmed, "Circle received.");
            }
        }
        graph_wait_vsync();
    }

    draw_screen(return_selected, confirmed, "Returning to Ibara...");
    padPortClose(0, 0);
    padEnd();
    LoadExecPS2(retail_path, 0, NULL);
}
