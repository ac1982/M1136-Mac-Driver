/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef M1136_IO_H
#define M1136_IO_H
#include <signal.h>
#include <stddef.h>
#include <sys/types.h>
/* Descriptors must be nonblocking. Returns one syscall's transfer count. */
ssize_t m1136_io(int fd, void *data, size_t size, int writing,
                 volatile sig_atomic_t *cancelled);
#endif
