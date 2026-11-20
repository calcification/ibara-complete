#include "cv1k_memory.h"
#ifdef IC_FREESTANDING
/* Declarations of libc routines that a PS2SDK project supplies at link time. */
void *memcpy(void *dst, const void *src, size_t count);
void *memset(void *dst, int value, size_t count);
#else
#include <string.h>
#endif

/* A tile is the minimum allocated working set. This model intentionally does
 * NOT evict dirty tiles; if Kuro exceeds the budget, report the failure. */
static int in_bounds(uint16_t x, uint16_t y) { return x < IC_VRAM_WIDTH && y < IC_VRAM_HEIGHT; }
static uint32_t tile_index(uint16_t x, uint16_t y) {
    return (uint32_t)(y / IC_TILE_EDGE) * IC_TILES_X + x / IC_TILE_EDGE;
}
static uint32_t pixel_index(uint16_t x, uint16_t y) {
    return (uint32_t)(y % IC_TILE_EDGE) * IC_TILE_EDGE + x % IC_TILE_EDGE;
}
int ic_vram_init(ic_vram *v, uint16_t *buf, uint16_t cap) {
    if (!v || !buf || cap == 0 || cap >= IC_TILE_EMPTY) return -1;
    memset(v, 0, sizeof(*v));
    memset(v->map, 0xFF, sizeof(v->map));
    v->pixels = buf;
    v->capacity = cap;
    return 0;
}
int ic_vram_write(ic_vram *v, uint16_t x, uint16_t y, uint16_t p) {
    uint32_t ix, off;
    uint16_t tile;
    if (!v || !in_bounds(x, y)) { if (v) v->out_of_bounds++; return -1; }
    ix = tile_index(x, y);
    tile = v->map[ix];
    if (tile == IC_TILE_EMPTY) {
        if (!p) { v->writes++; return 0; } /* don't allocate for zero-only touches */
        if (v->used >= v->capacity) { v->out_of_tiles++; return -2; }
        tile = v->used++;
        v->map[ix] = tile;
        memset(v->pixels + (size_t)tile * IC_TILE_PIXELS, 0, IC_TILE_BYTES);
        if (v->used > v->high_water) v->high_water = v->used;
    }
    off = (uint32_t)tile * IC_TILE_PIXELS + pixel_index(x, y);
    v->pixels[off] = p;
    v->writes++;
    return 0;
}
int ic_vram_read(ic_vram *v, uint16_t x, uint16_t y, uint16_t *p) {
    uint16_t tile;
    if (!v || !p || !in_bounds(x, y)) { if (v) v->out_of_bounds++; return -1; }
    tile = v->map[tile_index(x, y)];
    *p = tile == IC_TILE_EMPTY ? 0 : v->pixels[(uint32_t)tile * IC_TILE_PIXELS + pixel_index(x, y)];
    v->read_count++;
    return 0;
}
int ic_vram_rect_fill(ic_vram *v, uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint16_t p) {
    uint32_t yy, xx;
    if (!v || (uint32_t)x+w > IC_VRAM_WIDTH || (uint32_t)y+h > IC_VRAM_HEIGHT) return -1;
    for (yy = y; yy < (uint32_t)y+h; yy++)
        for (xx = x; xx < (uint32_t)x+w; xx++)
            if (ic_vram_write(v, (uint16_t)xx, (uint16_t)yy, p)) return -2;
    return 0;
}
int ic_vram_copy(ic_vram *v, uint16_t sx, uint16_t sy, uint16_t dx, uint16_t dy, uint16_t w, uint16_t h) {
    /* Memmove-equivalent for a single 2-D rectangle; bounds checked first. */
    uint32_t ry, rx;
    if (!v || (uint32_t)sx+w > IC_VRAM_WIDTH || (uint32_t)dx+w > IC_VRAM_WIDTH ||
        (uint32_t)sy+h > IC_VRAM_HEIGHT || (uint32_t)dy+h > IC_VRAM_HEIGHT) return -1;
    for (ry = 0; ry < h; ry++) {
        uint32_t y = dy > sy ? h - 1u - ry : ry;
        for (rx = 0; rx < w; rx++) {
            uint32_t x = ((dy == sy || (uint32_t)sy+y == (uint32_t)dy+y) && dx > sx) ? w-1u-rx : rx;
            uint16_t p;
            if (ic_vram_read(v, (uint16_t)(sx+x), (uint16_t)(sy+y), &p) ||
                ic_vram_write(v, (uint16_t)(dx+x), (uint16_t)(dy+y), p)) return -2;
        }
    }
    return 0;
}
size_t ic_vram_bytes_used(const ic_vram *v) {
    return v ? (size_t)v->used * IC_TILE_BYTES + sizeof(v->map) : 0;
}
int ic_nand_init(ic_nand_cache *n, ic_nand_line *lines, uint16_t nl, ic_nand_fetch_fn fetch, void *opaque) {
    uint32_t i;
    if (!n || !lines || nl == 0 || !fetch) return -1;
    memset(n, 0, sizeof(*n));
    n->lines=lines; n->nlines=nl; n->fetch=fetch; n->opaque=opaque;
    for (i=0;i<nl;i++) { lines[i].page=UINT32_MAX; lines[i].age=0; }
    return 0;
}
static ic_nand_line *get_line(ic_nand_cache *n, uint32_t page) {
    uint32_t i, choose=0, oldest=UINT32_MAX;
    for (i=0;i<n->nlines;i++) {
        if (n->lines[i].page==page) {
            n->hits++; n->lines[i].age=++n->ticks; return &n->lines[i];
        }
        if (n->lines[i].page==UINT32_MAX) { choose=i; oldest=0; break; }
        if (n->lines[i].age<oldest) { oldest=n->lines[i].age; choose=i; }
    }
    (void)oldest;
    if (n->fetch(n->opaque,page,n->lines[choose].data)) return NULL;
    n->misses++; n->lines[choose].page=page; n->lines[choose].age=++n->ticks;
    return &n->lines[choose];
}
int ic_nand_read(ic_nand_cache *n, uint32_t pos, void *out, size_t len) {
    uint8_t *dst=(uint8_t*)out;
    if (!n || (!out && len) || (uint64_t)pos+len > IC_NAND_LENGTH) return -1;
    while (len) {
        const uint32_t page=pos/IC_NAND_PAGE_SIZE;
        const uint32_t off=pos%IC_NAND_PAGE_SIZE;
        const size_t take=(IC_NAND_PAGE_SIZE-off < len) ? IC_NAND_PAGE_SIZE-off : len;
        ic_nand_line *line=get_line(n,page);
        if (!line) return -2;
        memcpy(dst,line->data+off,take);
        dst+=take; pos+=(uint32_t)take; len-=take;
        n->bytes_returned+=take;
    }
    return 0;
}
