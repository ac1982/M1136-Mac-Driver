/* SPDX-License-Identifier: GPL-2.0-or-later */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"line %d: %s\n",__LINE__,#x); exit(1); } } while(0)
static volatile sig_atomic_t cancelled;
static int inject_syscall, inject_poll;
static void cancel(int sig) { (void)sig; cancelled=1; }
static ssize_t test_read(int fd, void *p, size_t n) {
    if(inject_syscall) raise(SIGTERM);
    return read(fd,p,n);
}
static ssize_t test_write(int fd, const void *p, size_t n) {
    if(inject_syscall) raise(SIGTERM);
    return write(fd,p,n);
}
static int test_poll(struct pollfd *p, nfds_t n, int timeout) {
    if(inject_poll) raise(SIGTERM);
    return poll(p,n,timeout);
}
/* Inject the signal after the cancellation check, before the actual syscall. */
#define read test_read
#define write test_write
#define poll test_poll
#include "../src/io.c"
#undef read
#undef write
#undef poll
int main(void) {
    struct sigaction a={0}; a.sa_handler=cancel;
    CHECK(!sigaction(SIGTERM,&a,NULL));
    int fds[2]; CHECK(!pipe(fds));
    for(int i=0;i<2;++i) CHECK(fcntl(fds[i],F_SETFL,O_NONBLOCK)>=0);
    char data[4096]={0};
    for(int writing=0;writing<=1;++writing) {
        if(writing) {
            while(write(fds[1],data,sizeof data)>0) {}
            CHECK(errno==EAGAIN || errno==EWOULDBLOCK);
        }
        for(int mode=0;mode<2;++mode) {
            cancelled=0; inject_syscall=!mode; inject_poll=mode;
            CHECK(m1136_io(fds[writing],data,sizeof data,writing,&cancelled)==-1);
            CHECK(cancelled && errno==EINTR);
        }
    }
    inject_syscall=inject_poll=0; cancelled=0;
    CHECK(m1136_io(fds[0],data,sizeof data,0,&cancelled)>0);
    CHECK(m1136_io(fds[1],data,1,1,&cancelled)==1);
    close(fds[0]);close(fds[1]);
    puts("read/write and poll cancellation races PASS");
    return 0;
}
