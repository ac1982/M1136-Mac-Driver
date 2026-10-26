/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef M1136_DUPLEX_H
#define M1136_DUPLEX_H
#include "m1136.h"
#include <signal.h>
#include <sys/types.h>
#define M1136_DUPLEX_PAGES 200u /* 100-sheet output tray */
typedef struct {
    off_t offset, length;
    m1136_page shape;
    unsigned paper;
} m1136_saved_page;
typedef struct {
    int fd, mode;
    unsigned count;
    off_t bytes;
    volatile sig_atomic_t *cancelled;
    m1136_saved_page pages[M1136_DUPLEX_PAGES];
} m1136_duplex;
int m1136_duplex_add(m1136_duplex *, m1136_page *, unsigned);
int m1136_duplex_print(m1136_duplex *, m1136_job *);
void m1136_rotate(m1136_page *, volatile sig_atomic_t *);
#endif
