/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef M1136_RASTER_INPUT_H
#define M1136_RASTER_INPUT_H
#include <cups/raster.h>
#include <signal.h>
#include <stddef.h>
typedef struct {
    int fd, failed, swapped;
    size_t header_size, position, available;
    unsigned char pending[sizeof(cups_page_header2_t)];
    volatile sig_atomic_t *cancelled;
    cups_raster_t *reader;
    const char *error;
} m1136_raster;
int m1136_raster_open(m1136_raster *, int, volatile sig_atomic_t *);
/* 1=valid header, 0=clean EOF, -1=error. Validates before CUPS allocates. */
int m1136_raster_next(m1136_raster *, cups_page_header2_t *, unsigned *);
unsigned m1136_raster_pixels(m1136_raster *, unsigned char *, unsigned);
void m1136_raster_close(m1136_raster *);
#endif
