#include <debug.h>
#include <fcntl.h>
#include <iopcontrol.h>
#include <kernel.h>
#include <sifrpc.h>
#include <unistd.h>

static unsigned char data[5120] __attribute__((aligned(64)));

static int read_file(const char *path)
{
    int fd = open(path, O_RDONLY);
    if (fd < 0)
        return fd;
    int length = read(fd, data, sizeof(data));
    close(fd);
    return length;
}

int main(void)
{
    sceSifInitRpc(0);
    while (!SifIopReset(NULL, 0)) {
    }
    while (!SifIopSync()) {
    }
    sceSifInitRpc(0);
    init_scr();
    scr_setCursor(0);
    scr_setXY(6, 4);
    scr_printf("Companion disc file test\n\n");
    int pattern = read_file("cdrom0:\\PROBE.DAT;1");
    int ok = pattern == 5000;
    for (int i = 0; ok && i < pattern; ++i)
        ok = data[i] == (unsigned char)(17 * i + 3);
    scr_printf("PROBE.DAT: %s (%d bytes)\n", ok ? "PASS" : "FAIL", pattern);
    int empty = read_file("cdrom0:\\EMPTY;1");
    scr_printf("EMPTY: %s (%d bytes)\n", empty == 0 ? "PASS" : "FAIL", empty);
    scr_printf("\n%s\n", ok && empty == 0 ? "BOTH COMPANIONS VERIFIED" : "COMPANION CHECK FAILED");
    SleepThread();
    return 0;
}
