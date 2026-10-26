/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifdef __APPLE__
#define _DARWIN_C_SOURCE
#else
#define _POSIX_C_SOURCE 200809L
#endif
#include "raster_input.h"
#include "m1136.h"
#include <errno.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>

_Static_assert(sizeof(cups_page_header_t)==420, "CUPS v1 wire header changed");
_Static_assert(sizeof(cups_page_header2_t)==1796, "CUPS v3 wire header changed");

static ssize_t read_fd(m1136_raster *r, unsigned char *data, size_t n)
{
    if(*r->cancelled) { r->failed=1; return -1; }
    ssize_t count;
    do { count=read(r->fd,data,n); } while(count<0 && errno==EINTR && !*r->cancelled);
    if(count<0 || *r->cancelled) { r->failed=1; return -1; }
    return count;
}
/* Read only requested bytes: no lookahead past the current page. */
static ssize_t read_exact(m1136_raster *r, unsigned char *data, size_t n)
{
    size_t got=0;
    while(got<n) {
        ssize_t count=read_fd(r,data+got,n-got);
        if(count<0) return -1;
        if(!count) break;
        got+=(size_t)count;
    }
    return (ssize_t)got;
}
static ssize_t read_cups(void *context, unsigned char *data, size_t n)
{
    m1136_raster *r=context;
    if(*r->cancelled || r->failed) return 0;
    if(r->position<r->available) {
        size_t count=r->available-r->position;
        if(count>n) count=n;
        memcpy(data,r->pending+r->position,count);r->position+=count;
        return (ssize_t)count;
    }
    ssize_t count=read_fd(r,data,n);
    return count<0 ? 0 : count;
}
int m1136_raster_open(m1136_raster *r, int fd, volatile sig_atomic_t *cancelled)
{
    *r=(m1136_raster){.fd=fd,.cancelled=cancelled};
    if(read_exact(r,r->pending,4)!=4) { r->error="Missing raster magic"; return -1; }
    uint32_t magic;memcpy(&magic,r->pending,4);
    if(magic==CUPS_RASTER_SYNC || magic==CUPS_RASTER_REVSYNC) r->header_size=1796;
    else if(magic==CUPS_RASTER_SYNCv1 || magic==CUPS_RASTER_REVSYNCv1) r->header_size=420;
    else {r->error="Expected uncompressed CUPS raster v1/v3";return -1;}
    r->swapped=magic==CUPS_RASTER_REVSYNC || magic==CUPS_RASTER_REVSYNCv1;
    r->available=4;
    r->reader=cupsRasterOpenIO(read_cups,r,CUPS_RASTER_READ);
    if(!r->reader) {r->error="Cannot open CUPS raster reader";return -1;}
    return 0;
}
static uint32_t field(const m1136_raster *r, size_t offset)
{
    uint32_t value;memcpy(&value,r->pending+offset,4);
    if(r->swapped) value=(value>>24)|((value>>8)&0xff00)|((value<<8)&0xff0000)|(value<<24);
    return value;
}
#define FIELD(r, name) field((r),offsetof(cups_page_header2_t,name))
int m1136_raster_next(m1136_raster *r, cups_page_header2_t *h, unsigned *paper)
{
    if(r->failed) {r->error="Raster input failed";return -1;}
    ssize_t count=read_exact(r,r->pending,r->header_size);
    if(!count) return 0;
    if(count!=(ssize_t)r->header_size) {r->error="Truncated or unreadable page header";return -1;}
    uint32_t w=FIELD(r,cupsWidth),height=FIELD(r,cupsHeight),stride=FIELD(r,cupsBytesPerLine);
    unsigned colors=r->header_size==420 ? 1 : FIELD(r,cupsNumColors);
    if(!w || w>M1136_MAX_WIDTH || !height || height>M1136_MAX_HEIGHT ||
       stride<w || stride>8192 || FIELD(r,HWResolution[0])!=600 || FIELD(r,HWResolution[1])!=600 ||
       FIELD(r,cupsColorOrder)!=CUPS_ORDER_CHUNKED || colors!=1 ||
       FIELD(r,cupsBitsPerColor)!=8 || FIELD(r,cupsBitsPerPixel)!=8 ||
       FIELD(r,cupsColorSpace)!=CUPS_CSPACE_W || FIELD(r,Duplex) || FIELD(r,Tumble)) {
        r->error="Expected bounded 600dpi, 8-bit white grayscale, simplex raster";return -1;
    }
    unsigned pw=FIELD(r,PageSize[0]),ph=FIELD(r,PageSize[1]);
    if(pw==595 && ph==842) *paper=9;
    else if(pw==612 && ph==792) *paper=1;
    else {r->error="Only A4 and Letter are supported";return -1;}
    r->position=0;r->available=r->header_size;
    if(!cupsRasterReadHeader2(r->reader,h) || r->failed || r->position!=r->available) {
        r->error="CUPS rejected raster page header";return -1;
    }
    return 1;
}
unsigned m1136_raster_pixels(m1136_raster *r, unsigned char *data, unsigned n)
{ return cupsRasterReadPixels(r->reader,data,n); }
void m1136_raster_close(m1136_raster *r)
{ if(r->reader) cupsRasterClose(r->reader);r->reader=NULL; }
