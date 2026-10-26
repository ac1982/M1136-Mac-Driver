/* SPDX-License-Identifier: GPL-2.0-or-later */
#define _POSIX_C_SOURCE 200809L
#include "m1136.h"
#include <cups/raster.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t cancelled;
static void cancel_job(int signal_number) { (void)signal_number; cancelled = 1; }
/* Only uncompressed CUPS v1/v3: the system reader does no read-ahead here.
 * Tracking bytes distinguishes EOF from a partially read next-page header. */
typedef struct { int fd, first, failed; size_t bytes; } raster_input;
static ssize_t read_input(void *context, unsigned char *buffer, size_t size)
{
    raster_input *in=context;
    if(cancelled) { in->failed=1; return 0; }
    ssize_t n;
    if(in->first && size==4) {
        size_t got=0;
        while(got<4 && !cancelled) {
            do { n=read(in->fd,buffer+got,4-got); } while(n<0 && errno==EINTR && !cancelled);
            if(n<=0) break;
            got+=(size_t)n;
        }
        n=(ssize_t)got;
    } else {
        do { n=read(in->fd,buffer,size); } while(n<0 && errno==EINTR && !cancelled);
    }
    if(n<0 || cancelled) { in->failed=1; return 0; }
    if(in->first) {
        /* cupsRasterOpenIO requests the four-byte sync word first. */
        if(size!=4 || n!=4) { in->failed=1; return 0; }
        uint32_t magic; memcpy(&magic,buffer,4);
        if(magic!=CUPS_RASTER_SYNC && magic!=CUPS_RASTER_REVSYNC &&
           magic!=CUPS_RASTER_SYNCv1 && magic!=CUPS_RASTER_REVSYNCv1) {
            in->failed=1; return 0;
        }
        in->first=0;
    }
    in->bytes+=(size_t)n;
    return n;
}
static int write_output(void *unused, const void *data, size_t size)
{
    (void)unused;
    const unsigned char *p = data;
    while (size && !cancelled) {
        ssize_t n = write(STDOUT_FILENO, p, size);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return -1;
        p += (size_t)n; size -= (size_t)n;
    }
    return cancelled ? -1 : 0;
}
static int copies_arg(const char *s, unsigned *copies)
{
    if (!s || !*s) return -1;
    unsigned n=0;
    for (; *s; ++s) {
        if (*s<'0' || *s>'9' || n>99) return -1;
        n=n*10+(unsigned)(*s-'0');
    }
    if (n<1 || n>99) return -1;
    *copies=n; return 0;
}
static unsigned paper_code(const cups_page_header2_t *h)
{
    if (h->HWResolution[0]!=600 || h->HWResolution[1]!=600 ||
        h->cupsColorOrder!=CUPS_ORDER_CHUNKED || h->cupsNumColors!=1 ||
        h->cupsBitsPerColor!=8 || h->cupsBitsPerPixel!=8 ||
        h->cupsColorSpace!=CUPS_CSPACE_W || h->cupsBytesPerLine<h->cupsWidth ||
        h->cupsBytesPerLine>8192 || h->Duplex || h->Tumble ||
        !h->cupsWidth || h->cupsWidth>M1136_MAX_WIDTH ||
        !h->cupsHeight || h->cupsHeight>M1136_MAX_HEIGHT) return 0;
    if(h->PageSize[0]==595 && h->PageSize[1]==842) return 9;
    if(h->PageSize[0]==612 && h->PageSize[1]==792) return 1;
    return 0;
}
int main(int argc, char **argv)
{
    const char *error=NULL;
    int status=1, fd=STDIN_FILENO;
    unsigned copies;
    cups_raster_t *raster=NULL;
    m1136_page page={0}; m1136_job job={0};
    unsigned char row[8192];
    struct rlimit core={0,0};
    if(setrlimit(RLIMIT_CORE,&core)) { error="Cannot disable core dumps"; goto done; }
    struct sigaction action={0};
    sigemptyset(&action.sa_mask); action.sa_handler=cancel_job;
    if(sigaction(SIGTERM,&action,NULL) || sigaction(SIGINT,&action,NULL)) {
        error="Cannot install cancellation handler"; goto done;
    }
    action.sa_handler=SIG_IGN;
    if(sigaction(SIGPIPE,&action,NULL)) { error="Cannot handle broken pipe"; goto done; }
    if((argc!=6 && argc!=7) || copies_arg(argv[4],&copies)) {
        error="Expected CUPS arguments and copy count 1..99"; goto done;
    }
    /* Titles, usernames and arbitrary option strings never enter PJL or a shell. */
    if(argc==7) {
        fd=open(argv[6],O_RDONLY|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK);
        struct stat st;
        if(fd<0 || fstat(fd,&st) || !S_ISREG(st.st_mode)) {
            error="Input must be a regular non-symlink spool file"; goto done;
        }
    }
    raster_input input={fd,1,0,0};
    raster=cupsRasterOpenIO(read_input,&input,CUPS_RASTER_READ);
    if(!raster) { error="Cannot open CUPS raster"; goto done; }
    cups_page_header2_t header;
    while(!cancelled) {
        size_t before=input.bytes;
        if(!cupsRasterReadHeader2(raster,&header)) {
            if(input.failed || input.bytes!=before) {
                error="Truncated, invalid or unreadable raster header"; goto done;
            }
            break;
        }
        unsigned paper=paper_code(&header);
        if(!paper) { error="Expected A4/Letter, 600dpi, 8-bit white grayscale, simplex"; goto done; }
        if(job.pages>=M1136_MAX_PAGES) { error="Job exceeds 500 pages"; goto done; }
        m1136_result result=m1136_page_create(&page,header.cupsWidth,header.cupsHeight);
        if(result) { error=m1136_error(result); goto done; }
        for(unsigned y=0;y<header.cupsHeight;++y) {
            if(cancelled) { error="Job cancelled"; goto done; }
            if(cupsRasterReadPixels(raster,row,header.cupsBytesPerLine)!=header.cupsBytesPerLine) {
                error="Truncated or malformed raster pixels"; goto done;
            }
            result=m1136_page_row(&page,y,row,header.cupsBytesPerLine);
            if(result) { error=m1136_error(result); goto done; }
        }
        if(!job.active) {
            time_t now=time(NULL); struct tm local;
            char stamp[15];
            if(!localtime_r(&now,&local) || strftime(stamp,sizeof stamp,"%Y%m%d%H%M%S",&local)!=14) {
                error="Cannot format job timestamp"; goto done;
            }
            result=m1136_job_begin(&job,write_output,NULL,copies,stamp);
            if(result) { error=m1136_error(result); goto done; }
        }
        result=m1136_job_page(&job,&page,paper);
        if(result) { error=m1136_error(result); goto done; }
        fprintf(stderr,"PAGE: %u %u\n",job.pages,copies);
        m1136_page_destroy(&page);
    }
    if(cancelled) { error="Job cancelled"; goto done; }
    if(!job.pages) { error="Empty or invalid raster stream"; goto done; }
    const char *detail=cupsRasterErrorString();
    if(detail && *detail) { error="Malformed raster stream"; goto done; }
    m1136_result result=m1136_job_end(&job);
    if(result) { error=m1136_error(result); goto done; }
    status=0;
done:
    m1136_page_destroy(&page);
    if(raster) cupsRasterClose(raster);
    if(fd>=0 && fd!=STDIN_FILENO) close(fd);
    if(error) fprintf(stderr,"ERROR: %s\n",error);
    return status;
}
