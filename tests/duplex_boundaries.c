/* SPDX-License-Identifier: GPL-2.0-or-later */
#define _DARWIN_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#include "io.h"
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"line %d: %s\n",__LINE__,#x); exit(1); } } while (0)

/* Inject storage failure/cancellation at a deterministic read or write. */
static unsigned reads, writes, fail_read, cancel_read, cancel_write;
static ssize_t storage_io(int fd, void *p, size_t n, int writing,
                          volatile sig_atomic_t *cancelled)
{
    if(writing) {
        if(++writes==cancel_write) *cancelled=1;
    } else {
        ++reads;
        if(reads==fail_read) { errno=EIO; return -1; }
        if(reads==cancel_read) *cancelled=1;
    }
    return m1136_io(fd,p,n,writing,cancelled);
}
#define m1136_io storage_io
#include "../src/duplex.c"
#undef m1136_io

typedef struct { unsigned calls, fail; size_t bytes; int end; } sink;
static int output(void *context, const void *data, size_t n)
{
    sink *s=context;
    if(++s->calls==s->fail) return -1;
    s->bytes+=n;
    if(n>=16 && !memcmp(data,"\033%-12345X@PJL EOJ",16)) s->end=1;
    return 0;
}
static int print(m1136_duplex *d, sink *s)
{
    m1136_job job={0};
    if(m1136_job_begin_manual(&job,output,s,"20261026000000")) return -1;
    if(m1136_duplex_print(d,&job)) return -1;
    return m1136_job_end(&job) ? -1 : 0;
}

int main(void)
{
    volatile sig_atomic_t cancelled=0;
    m1136_duplex d={.fd=-1,.mode=1,.cancelled=&cancelled};
    m1136_page page={0};
    CHECK(!m1136_page_create(&page,129,32));
    page.bits[0]=0x80;
    CHECK(!m1136_duplex_add(&d,&page,9));
    CHECK(!m1136_duplex_add(&d,&page,9));
    struct stat st;
    CHECK(!fstat(d.fd,&st));
    CHECK((st.st_mode&0777)==0600 && st.st_nlink==0);

    sink s={0}; CHECK(!print(&d,&s) && s.end);
    unsigned calls=s.calls;
    for(unsigned fail=1;fail<=calls;++fail) {
        s=(sink){.fail=fail};
        CHECK(print(&d,&s)==-1 && s.calls==fail);
    }
    /* Fail on the first side or the back side; never emit a successful EOJ. */
    for(unsigned side=1;side<=2;++side) {
        reads=0;fail_read=side;s=(sink){0};
        CHECK(print(&d,&s)==-1 && !s.end && reads==side);
        fail_read=0;reads=0;cancel_read=side;s=(sink){0};
        CHECK(print(&d,&s)==-1 && !s.end && cancelled);
        cancel_read=0;cancelled=0;
    }
    s=(sink){0}; CHECK(!print(&d,&s) && s.end);
    CHECK(!ftruncate(d.fd,0));s=(sink){0};
    CHECK(print(&d,&s)==-1 && !s.end); /* unexpected EOF during replay */
    close(d.fd);

    /* Real sparse-file boundary: allocate only its final block, not 512 MiB. */
    d=(m1136_duplex){.fd=-1,.mode=1,.cancelled=&cancelled};
    CHECK(!m1136_duplex_add(&d,&page,9));
    const off_t limit=512u*1024u*1024u;
    CHECK(lseek(d.fd,limit-4,SEEK_SET)==limit-4);d.bytes=limit-4;
    CHECK(!save_bytes(&d,"tail",4) && d.bytes==limit);
    CHECK(save_bytes(&d,"x",1)==-1 && d.bytes==limit);
    CHECK(!fstat(d.fd,&st) && st.st_size==limit);
    close(d.fd);

    /* Cancellation after the loop guard but before the actual spool write. */
    d=(m1136_duplex){.fd=-1,.mode=1,.cancelled=&cancelled};
    writes=0;cancel_write=1;
    CHECK(m1136_duplex_add(&d,&page,9)==-1 && cancelled && d.count==0);
    CHECK(!fstat(d.fd,&st) && st.st_size==0 && st.st_nlink==0);
    close(d.fd);m1136_page_destroy(&page);
    puts("duplex: all output failures, front/back read failure and cancellation, truncated spool, private/unlinked file, exact 512 MiB cap PASS");
    return 0;
}
