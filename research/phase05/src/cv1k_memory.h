/* Ibara Complete - independent CV1000 low-memory feasibility prototype.
 * MIT-licensed original implementation; does not include game code/assets.
 * Diagnostic prototype, not a tested CV1000 renderer.
 */
#ifndef IBARA_CV1K_MEMORY_H
#define IBARA_CV1K_MEMORY_H
#include <stdint.h>
#include <stddef.h>

#define IC_VRAM_WIDTH 8192u
#define IC_VRAM_HEIGHT 4096u
#define IC_TILE_EDGE 64u
#define IC_TILE_PIXELS (IC_TILE_EDGE * IC_TILE_EDGE)
#define IC_TILE_BYTES (IC_TILE_PIXELS * 2u)
#define IC_TILES_X (IC_VRAM_WIDTH / IC_TILE_EDGE)
#define IC_TILES_Y (IC_VRAM_HEIGHT / IC_TILE_EDGE)
#define IC_TILE_COUNT (IC_TILES_X * IC_TILES_Y)
#define IC_TILE_EMPTY UINT16_MAX
#define IC_NAND_PAGE_SIZE 2112u
#define IC_NAND_MAIN_BYTES 2048u
#define IC_NAND_PAGE_COUNT 65536u
#define IC_NAND_LENGTH (IC_NAND_PAGE_SIZE * IC_NAND_PAGE_COUNT)

typedef struct {
    uint16_t map[IC_TILE_COUNT];  /* 0xffff = unwritten zero tile */
    uint16_t *pixels;             /* caller-owned, tile_count * 4096 pixels */
    uint16_t capacity;           /* 0..65534 resident tiles */
    uint16_t used;
    uint32_t writes, read_count;
    uint32_t out_of_bounds, out_of_tiles;
    uint32_t high_water;
} ic_vram;

/* Each tile is 8192 bytes; caller owns tiles_buf and chooses a memory budget.
 * All allocated tiles are initially zero, with no eviction: a diagnostic
 * bounded-memory model. Returns 0 on success, -1 on invalid argument. */
int ic_vram_init(ic_vram *v, uint16_t *tiles_buf, uint16_t capacity);
int ic_vram_write(ic_vram *v, uint16_t x, uint16_t y, uint16_t pixel);
int ic_vram_read(ic_vram *v, uint16_t x, uint16_t y, uint16_t *pixel);
int ic_vram_rect_fill(ic_vram *v, uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint16_t pixel);
int ic_vram_copy(ic_vram *v, uint16_t sx, uint16_t sy, uint16_t dx, uint16_t dy, uint16_t w, uint16_t h);
size_t ic_vram_bytes_used(const ic_vram *v);

typedef int (*ic_nand_fetch_fn)(void *opaque, uint32_t page, uint8_t dst[IC_NAND_PAGE_SIZE]);
typedef struct {
    uint32_t page;
    uint32_t age;
    uint8_t data[IC_NAND_PAGE_SIZE];
} ic_nand_line;
typedef struct {
    ic_nand_line *lines;    /* caller-owned, nlines entries */
    uint16_t nlines;
    uint32_t ticks;
    uint64_t hits, misses, bytes_returned;
    ic_nand_fetch_fn fetch;
    void *opaque;
} ic_nand_cache;
int ic_nand_init(ic_nand_cache *n, ic_nand_line *lines, uint16_t nlines, ic_nand_fetch_fn fetch, void *opaque);
int ic_nand_read(ic_nand_cache *n, uint32_t offset, void *dst, size_t length);

#endif
