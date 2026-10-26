/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef M1136_H
#define M1136_H
#include <stddef.h>
#include <stdint.h>
#define M1136_MAX_WIDTH 5200u
#define M1136_MAX_HEIGHT 8500u
#define M1136_MAX_PAGES 500u
/* Return zero only after writing the entire buffer. */
typedef int (*m1136_write_fn)(void *, const void *, size_t);
typedef enum { M1136_OK, M1136_INVALID, M1136_MEMORY, M1136_OUTPUT,
               M1136_STATE, M1136_CODEC } m1136_result;
typedef struct {
    uint32_t width, height;
    size_t stride;
    unsigned char *bits;
} m1136_page;
typedef struct {
    m1136_write_fn write;
    void *context;
    unsigned pages;
    int active;
    m1136_result error;
} m1136_job;
m1136_result m1136_page_create(m1136_page *, uint32_t, uint32_t);
m1136_result m1136_page_row(m1136_page *, uint32_t, const unsigned char *, size_t);
void m1136_page_destroy(m1136_page *);
m1136_result m1136_job_begin(m1136_job *, m1136_write_fn, void *, const char *);
m1136_result m1136_job_page(m1136_job *, const m1136_page *, unsigned paper, unsigned copies);
m1136_result m1136_job_end(m1136_job *);
const char *m1136_error(m1136_result);
#endif
