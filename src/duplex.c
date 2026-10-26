/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifdef __APPLE__
#define _DARWIN_C_SOURCE
#else
#define _POSIX_C_SOURCE 200809L
#endif
#include "duplex.h"
#include "internal.h"
#include "io.h"
#include <cups/cups.h>
#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>

/* Rotate the visible rectangle, not the JBIG alignment padding. */
void m1136_rotate(m1136_page *p, volatile sig_atomic_t *cancelled)
{
    size_t pixels=(size_t)p->width*p->height;
    for(size_t i=0;i<pixels/2 && !*cancelled;++i) {
        size_t k=pixels-1-i;
        size_t a=(i/p->width)*p->stride+(i%p->width)/8;
        size_t b=(k/p->width)*p->stride+(k%p->width)/8;
        unsigned char ma=(unsigned char)(0x80u>>(i%p->width%8));
        unsigned char mb=(unsigned char)(0x80u>>(k%p->width%8));
        if (!!(p->bits[a]&ma) != !!(p->bits[b]&mb)) {
            p->bits[a]^=ma; p->bits[b]^=mb;
        }
    }
}

static int save_bytes(void *context, const void *data, size_t size)
{
    m1136_duplex *d=context;
    /* Bound disk use even for incompressible pages. No named spool survives. */
    if(size > 512u*1024u*1024u-(size_t)d->bytes) return -1;
    const unsigned char *p=data;
    while(size && !*d->cancelled) {
        ssize_t n=m1136_io(d->fd,(void *)p,size,1,d->cancelled);
        if(n<=0) return -1;
        d->bytes+=n; p+=n; size-=(size_t)n;
    }
    return *d->cancelled ? -1 : 0;
}

int m1136_duplex_add(m1136_duplex *d, m1136_page *p, unsigned paper)
{
    if(d->count>=M1136_DUPLEX_PAGES || *d->cancelled) return -1;
    if(d->count && (p->width!=d->pages[0].shape.width ||
       p->height!=d->pages[0].shape.height || paper!=d->pages[0].paper)) return -1;
    if(d->fd<0) {
        char path[1024];
        d->fd=cupsTempFd(path,sizeof path);
        if(d->fd<0) return -1;
        if(unlink(path) || fcntl(d->fd,F_SETFD,FD_CLOEXEC)<0) return -1;
    }
    if(d->mode==1 && (d->count&1)) m1136_rotate(p,d->cancelled);
    m1136_saved_page *saved=&d->pages[d->count];
    *saved=(m1136_saved_page){d->bytes,0,*p,paper};
    saved->shape.bits=NULL;
    m1136_job encoder={save_bytes,d,0,1,M1136_OK};
    if(m1136_encode(&encoder,p)) return -1;
    saved->length=d->bytes-saved->offset;
    ++d->count;
    return 0;
}

static int replay(m1136_duplex *d, m1136_job *job, unsigned index, int pause)
{
    m1136_saved_page *p=&d->pages[index];
    if(lseek(d->fd,p->offset,SEEK_SET)<0 ||
       m1136_page_header(job,&p->shape,p->paper,1,pause)) return -1;
    unsigned char block[65536];
    off_t left=p->length;
    while(left && !*d->cancelled) {
        size_t size=left>(off_t)sizeof block ? sizeof block : (size_t)left;
        ssize_t n=m1136_io(d->fd,block,size,0,d->cancelled);
        if(n<=0) return -1;
        m1136_bytes(job,block,(size_t)n);
        if(job->error) return -1;
        left-=n;
    }
    if(*d->cancelled || m1136_page_finish(job)) return -1;
    fprintf(stderr,"PAGE: %u 1\n",job->pages);
    return 0;
}

int m1136_duplex_print(m1136_duplex *d, m1136_job *job)
{
    for(unsigned i=0;i<d->count;i+=2)
        if(replay(d,job,i,i ? 1 : 0)) return -1;
    fprintf(stderr,"INFO: Manual duplex: wait for H1; reload the entire stack printed-side down without changing orientation, then press Copy.\n");
    for(unsigned i=d->count;i>0;i-=2)
        if(replay(d,job,i-1,i==d->count ? 2 : 3)) return -1;
    return 0;
}
