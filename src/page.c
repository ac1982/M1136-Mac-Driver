/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "m1136.h"
#include <stdlib.h>
#include <string.h>

m1136_result m1136_page_create(m1136_page *p, uint32_t w, uint32_t h)
{
    if (!p) return M1136_INVALID;
    *p = (m1136_page){0};
    if (!w || w > M1136_MAX_WIDTH || !h || h > M1136_MAX_HEIGHT)
        return M1136_INVALID;
    size_t stride = ((size_t)w + 127) / 128 * 16;
    unsigned char *bits = calloc(h, stride);
    if (!bits) return M1136_MEMORY;
    *p = (m1136_page){w, h, stride, bits};
    return M1136_OK;
}

m1136_result m1136_page_row(m1136_page *p, uint32_t y,
                            const unsigned char *gray, size_t length)
{
    static const unsigned char bayer[4][4] = {
        {0,8,2,10}, {12,4,14,6}, {3,11,1,9}, {15,7,13,5}
    };
    if (!p || !p->bits || !gray || y >= p->height || length < p->width)
        return M1136_INVALID;
    unsigned char *row = p->bits + (size_t)y * p->stride;
    memset(row, 0, p->stride);
    for (uint32_t x = 0; x < p->width; ++x)
        if (gray[x] < 8 + 16 * bayer[y % 4][x % 4])
            row[x / 8] |= (unsigned char)(0x80u >> (x % 8));
    return M1136_OK;
}

void m1136_page_destroy(m1136_page *p)
{
    if (p) { free(p->bits); *p = (m1136_page){0}; }
}

const char *m1136_error(m1136_result r)
{
    switch (r) {
    case M1136_OK: return "success";
    case M1136_INVALID: return "unsupported or invalid input";
    case M1136_MEMORY: return "out of memory";
    case M1136_OUTPUT: return "output failed or job cancelled";
    case M1136_STATE: return "invalid job state or page limit";
    case M1136_CODEC: return "invalid JBIG encoder output";
    }
    return "unknown error";
}
