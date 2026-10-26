/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "io.h"
#include <errno.h>
#include <poll.h>
#include <unistd.h>

ssize_t m1136_io(int fd, void *data, size_t size, int writing,
                 volatile sig_atomic_t *cancelled)
{
    while (!*cancelled) {
        ssize_t n = writing ? write(fd, data, size) : read(fd, data, size);
        if (n >= 0) return n;
        if (errno == EINTR) continue;
        if (errno != EAGAIN && errno != EWOULDBLOCK) return -1;
        struct pollfd p = {.fd=fd, .events=writing ? POLLOUT : POLLIN};
        /* A signal can arrive before poll starts. The finite timeout bounds
           that race even when no further input/output or signal arrives. */
        if (poll(&p, 1, 100) < 0 && errno != EINTR) return -1;
    }
    errno = EINTR;
    return -1;
}
