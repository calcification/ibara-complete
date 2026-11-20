#include <stddef.h>
#include <stdlib.h>

#include <debug.h>
#include <kernel.h>

int memory_selftest(void);

int main(void)
{
    const size_t mib = 1024 * 1024;
    const size_t work_bytes = 8 * mib;
    const size_t program_bytes = 2 * mib;
    const size_t video_bytes = 2 * 320 * 240 * 2;
    const size_t audio_bytes = mib / 2;
    const size_t reserved_bytes = work_bytes + program_bytes + video_bytes + audio_bytes;
    volatile unsigned char *reserve = malloc(reserved_bytes);

    init_scr();
    scr_setCursor(0);
    scr_setXY(6, 4);
    scr_printf("EE memory smoke test\n\n");
    if (reserve == NULL) {
        scr_printf("      FAIL: could not allocate the reserved buffers\n");
    } else {
        for (size_t offset = 0; offset < reserved_bytes; offset += 4096)
            reserve[offset] = (unsigned char)(offset >> 12);
        // The existing test allocates the tile pool and cache while these buffers are live.
        int result = memory_selftest();
        scr_printf("      %s: synthetic tile pool and cache\n", result == 0 ? "PASS" : "FAIL");
        scr_printf("      Reserved buffers: %u bytes\n", (unsigned)reserved_bytes);
        scr_printf("      Tile pool: 8 MiB, cache: 64 entries\n");
        free((void *)reserve);
    }
    SleepThread();
    return 0;
}
