/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "m1136.h"
#include "jbig.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #x); exit(1); } } while (0)
typedef struct { unsigned char *data; size_t size, capacity, calls, fail; } sink;
static int write_memory(void *context, const void *p, size_t n)
{
    sink *s = context;
    if (++s->calls == s->fail) return -1;
    if (s->size + n > s->capacity) {
        size_t cap = (s->size + n) * 2;
        void *new_data = realloc(s->data, cap);
        if (!new_data) return -1;
        s->data = new_data; s->capacity = cap;
    }
    memcpy(s->data + s->size, p, n); s->size += n;
    return 0;
}
static uint32_t u32(const unsigned char *p)
{ return (uint32_t)p[0]<<24 | (uint32_t)p[1]<<16 | (uint32_t)p[2]<<8 | p[3]; }
/* Independently parse XQX, reconstruct BIE, then decode and compare pixels. */
static void roundtrip(const sink *s, const m1136_page *page)
{
    size_t pos = 0; sink bie = {0};
    unsigned records[8] = {0};
    while (pos + 4 <= s->size && memcmp(s->data + pos, ",XQX", 4)) ++pos;
    CHECK(pos + 4 < s->size); pos += 4;
    int ended = 0;
    while (!ended) {
        CHECK(pos + 8 <= s->size);
        uint32_t type = u32(s->data + pos), count = u32(s->data + pos + 4); pos += 8;
        CHECK(type >= 1 && type <= 7); ++records[type];
        if (type == 7) {
            CHECK(count > 0 && count <= 65536 && count <= s->size-pos);
            CHECK(!write_memory(&bie, s->data+pos, count)); pos += count;
        } else {
            CHECK(count == (type == 1 ? 7u : type == 3 ? 15u : type == 5 ? 4u : 0u));
            for (uint32_t i=0; i<count; ++i) {
                CHECK(pos + 8 <= s->size);
                uint32_t key=u32(s->data+pos), n=u32(s->data+pos+4); pos+=8;
                CHECK(n <= s->size-pos);
                if (key == 0x40000002) {
                    CHECK(n==20 && bie.size==0);
                    CHECK(s->data[pos+16]==0 && s->data[pos+17]==0); /* MX/MY */
                    CHECK(!write_memory(&bie,s->data+pos,n));
                } else {
                    CHECK(n==4);
                    uint32_t v=u32(s->data+pos);
                    if (key==0x2000000d) CHECK(v==page->stride*8);
                    if (key==0x2000000f) CHECK(v==page->width);
                    if (key==0x2000000e || key==0x20000010) CHECK(v==page->height);
                    if (key==0x20000008 || key==0x20000009) CHECK(v==600);
                    if (key==0x80000001) CHECK(v==0xdeadbeef);
                }
                pos+=n;
            }
        }
        ended = type==2;
    }
    CHECK(records[1]==1 && records[2]==1 && records[3]==1 && records[4]==1);
    CHECK(records[5]==records[6] && records[6]==records[7]);
    if (page->width==1025) CHECK(records[7]>1); /* exercise continuation chunks */
    const char tail[]="\033%-12345X@PJL EOJ\n\033%-12345X";
    CHECK(s->size-pos==sizeof tail-1 && !memcmp(s->data+pos,tail,sizeof tail-1));
    struct jbg_dec_state d; size_t used=0;
    jbg_dec_init(&d);
    int result=jbg_dec_in(&d,bie.data,bie.size,&used);
    CHECK(result==JBG_EOK && used==bie.size);
    CHECK(jbg_dec_getwidth(&d)==page->stride*8 && jbg_dec_getheight(&d)==page->height);
    CHECK(jbg_dec_getsize(&d)==page->stride*page->height);
    CHECK(!memcmp(jbg_dec_getimage(&d,0),page->bits,page->stride*page->height));
    jbg_dec_free(&d); free(bie.data);
}
int main(void)
{
    m1136_page p={0};
    CHECK(m1136_page_create(&p,0,1)==M1136_INVALID);
    CHECK(m1136_page_create(&p,5201,1)==M1136_INVALID);
    CHECK(m1136_page_create(&p,1,8501)==M1136_INVALID);
    CHECK(m1136_page_create(&p,129,4)==M1136_OK);
    unsigned char row[129]; memset(row,255,sizeof row);
    CHECK(!m1136_page_row(&p,0,row,sizeof row));
    for (size_t i=0;i<p.stride;++i) CHECK(p.bits[i]==0);
    memset(row,0,sizeof row); CHECK(!m1136_page_row(&p,1,row,sizeof row));
    CHECK(p.bits[p.stride+16]==128 && p.bits[p.stride+17]==0);
    CHECK(m1136_page_row(&p,4,row,sizeof row)==M1136_INVALID);
    CHECK(m1136_page_row(&p,0,row,1)==M1136_INVALID);
    memset(row,128,sizeof row);
    for(unsigned y=0;y<4;++y) CHECK(!m1136_page_row(&p,y,row,sizeof row));
    unsigned black=0;
    for(unsigned y=0;y<4;++y) for(unsigned x=0;x<4;++x) black+=(p.bits[y*p.stride]>>(7-x))&1;
    CHECK(black==8);
    sink s={0}; m1136_job j={0};
    CHECK(m1136_job_end(&j)==M1136_STATE);
    CHECK(m1136_job_begin(&j,write_memory,&s,"PJL injection!")==M1136_INVALID);
    CHECK(!m1136_job_begin(&j,write_memory,&s,"20261026000000"));
    CHECK(!m1136_job_page(&j,&p,9,2)); CHECK(!m1136_job_end(&j)); roundtrip(&s,&p);
    size_t calls=s.calls; free(s.data);
    for(size_t fail=1;fail<=calls;++fail) {
        s=(sink){.fail=fail};
        m1136_result r=m1136_job_begin(&j,write_memory,&s,"20261026000000");
        if(!r) r=m1136_job_page(&j,&p,9,2);
        if(!r) r=m1136_job_end(&j);
        CHECK(r==M1136_OUTPUT && s.calls==fail);
        free(s.data);
    }
    s=(sink){0}; CHECK(!m1136_job_begin(&j,write_memory,&s,"20261026000000"));
    j.pages=500; CHECK(m1136_job_page(&j,&p,9,2)==M1136_STATE); free(s.data);
    for(unsigned copies=0; copies<=100; copies+=100) {
        s=(sink){0}; CHECK(!m1136_job_begin(&j,write_memory,&s,"20261026000000"));
        size_t before=s.size;
        CHECK(m1136_job_page(&j,&p,9,copies)==M1136_INVALID && s.size==before);
        CHECK(m1136_job_end(&j)==M1136_INVALID);
        free(s.data);
    }
    m1136_page_destroy(&p);
    /* Deterministic noisy image: crosses multiple 64 KiB chunks. */
    CHECK(!m1136_page_create(&p,1025,1024));
    uint32_t seed=17;
    for(size_t i=0;i<p.stride*p.height;++i) { seed=seed*1664525u+1013904223u; p.bits[i]=(unsigned char)(seed>>24); }
    s=(sink){0}; CHECK(!m1136_job_begin(&j,write_memory,&s,"20261026000000"));
    CHECK(!m1136_job_page(&j,&p,1,99)); CHECK(!m1136_job_end(&j)); roundtrip(&s,&p);
    free(s.data); m1136_page_destroy(&p);
    puts("core: dithering, geometry, state, every-write failures, XQX and JBIG roundtrip PASS");
    return 0;
}
