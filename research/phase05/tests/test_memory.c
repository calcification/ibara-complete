#include "../src/cv1k_memory.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

static int fake_page(void *unused,uint32_t page,uint8_t dst[IC_NAND_PAGE_SIZE]){
    unsigned i; (void)unused;
    for(i=0;i<IC_NAND_PAGE_SIZE;i++) dst[i]=(uint8_t)((page*17+i*3)&255);
    return 0;
}
int main(void) {
    const size_t cap=1024; /* 8 MiB storage vs 64 MiB linear VRAM */
    ic_vram *v=(ic_vram*)calloc(1,sizeof(*v));
    uint16_t *pool=(uint16_t*)calloc(cap,IC_TILE_BYTES);
    ic_nand_cache *n=(ic_nand_cache*)calloc(1,sizeof(*n));
    ic_nand_line *lines=(ic_nand_line*)calloc(64,sizeof(*lines));
    uint16_t p=0; uint8_t buf[6000]; size_t i;
    assert(v&&pool&&n&&lines);
    assert(ic_vram_init(v,pool,(uint16_t)cap)==0);
    assert(ic_vram_read(v,8191,4095,&p)==0 && p==0);
    assert(ic_vram_write(v,8191,4095,0xA3B5)==0);
    assert(ic_vram_read(v,8191,4095,&p)==0 && p==0xA3B5);
    assert(ic_vram_rect_fill(v,40,40,90,20,0x1234)==0);
    assert(ic_vram_copy(v,40,40,48,43,90,20)==0); /* overlap */
    assert(ic_vram_read(v,137,62,&p)==0 && p==0x1234);
    assert(ic_vram_copy(v,48,43,48,44,90,20)==0); /* vertical overlap */
    assert(ic_vram_read(v,137,63,&p)==0 && p==0x1234);
    assert(ic_vram_read(v,39,39,&p)==0 && p==0);
    assert(ic_vram_write(v,8192,4,2)==-1);
    /* Model must fail explicitly when tile budget is exceeded, not corrupt RAM. */
    {
        uint16_t one_tile[IC_TILE_PIXELS];
        ic_vram *tiny=(ic_vram*)calloc(1,sizeof(*tiny));
        assert(tiny && ic_vram_init(tiny,one_tile,1)==0);
        assert(ic_vram_write(tiny,1,1,0)==0 && tiny->used==0); /* implicit zero */
        assert(ic_vram_write(tiny,1,1,3)==0 && tiny->used==1);
        assert(ic_vram_write(tiny,100,1,4)==-2 && tiny->out_of_tiles==1);
        assert(ic_vram_read(tiny,100,1,&p)==0 && p==0);
        assert(ic_vram_read(tiny,1,1,&p)==0 && p==3);
        free(tiny);
    }
    assert(ic_nand_init(n,lines,64,fake_page,NULL)==0);
    assert(ic_nand_read(n,2090,buf,sizeof(buf))==0); /* crosses 4 pages */
    for(i=0;i<sizeof(buf);i++){unsigned pos=2090+i;assert(buf[i]==(uint8_t)((pos/2112*17+(pos%2112)*3)&255));}
    assert(n->misses==4);
    assert(ic_nand_read(n,2090,buf,sizeof(buf))==0);
    assert(n->misses==4 && n->hits==4);
    /* Eviction test uses two lines to force reuse. */
    assert(ic_nand_init(n,lines,2,fake_page,NULL)==0);
    assert(ic_nand_read(n,0,buf,1)==0);
    assert(ic_nand_read(n,2112,buf,1)==0);
    assert(ic_nand_read(n,0,buf,1)==0);       /* page 0 becomes MRU */
    assert(ic_nand_read(n,4224,buf,1)==0);    /* evicts page 1 */
    assert(ic_nand_read(n,2112,buf,1)==0);    /* misses again */
    assert(n->misses==4 && n->hits==1);
    printf("PASS: VRAM pixels / overlapping copies / bounds / pool overflow / NAND boundary + LRU\n");
    printf("VRAM: %u allocated tiles, %zu bytes including map; NAND: %llu hits %llu misses, %zu bytes of cache entries\n",
           v->used,ic_vram_bytes_used(v),(unsigned long long)n->hits,(unsigned long long)n->misses,64*sizeof(*lines));
    free(v);free(pool);free(n);free(lines);
    return 0;
}
