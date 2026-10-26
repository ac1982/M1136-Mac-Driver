/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifdef __APPLE__
#define _DARWIN_C_SOURCE
#else
#define _POSIX_C_SOURCE 200809L
#endif
#include "m1136.h"
#include "raster_input.h"
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
int main(int argc, char **argv)
{
    const char *error=NULL;
    int status=1, fd=STDIN_FILENO;
    unsigned copies;
    m1136_raster raster={0};
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
    if(m1136_raster_open(&raster,fd,&cancelled)) { error=raster.error; goto done; }
    cups_page_header2_t header;
    while(!cancelled) {
        unsigned paper=0;
        int next=m1136_raster_next(&raster,&header,&paper);
        if(next<0) {error=raster.error;goto done;}
        if(!next) break;
        if(job.pages>=M1136_MAX_PAGES) { error="Job exceeds 500 pages"; goto done; }
        m1136_result result=m1136_page_create(&page,header.cupsWidth,header.cupsHeight);
        if(result) { error=m1136_error(result); goto done; }
        for(unsigned y=0;y<header.cupsHeight;++y) {
            if(cancelled) { error="Job cancelled"; goto done; }
            if(m1136_raster_pixels(&raster,row,header.cupsBytesPerLine)!=header.cupsBytesPerLine) {
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
            result=m1136_job_begin(&job,write_output,NULL,stamp);
            if(result) { error=m1136_error(result); goto done; }
        }
        /* The renderer may expand collated copies; argv[4] is not the per-page copy count. */
        result=m1136_job_page(&job,&page,paper,header.NumCopies);
        if(result) { error=m1136_error(result); goto done; }
        fprintf(stderr,"PAGE: %u %u\n",job.pages,header.NumCopies);
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
    m1136_raster_close(&raster);
    if(fd>=0 && fd!=STDIN_FILENO) close(fd);
    if(error) fprintf(stderr,"ERROR: %s\n",error);
    return status;
}
