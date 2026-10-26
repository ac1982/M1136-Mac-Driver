/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "internal.h"
#include <stdio.h>
#include <string.h>

void m1136_bytes(m1136_job *j, const void *data, size_t n)
{
    if (j->error == M1136_OK && j->write(j->context, data, n))
        j->error = M1136_OUTPUT;
}
void m1136_u32(m1136_job *j, uint32_t n)
{
    unsigned char b[4] = {(unsigned char)(n >> 24), (unsigned char)(n >> 16),
                          (unsigned char)(n >> 8), (unsigned char)n};
    m1136_bytes(j, b, sizeof b);
}
void m1136_record(m1136_job *j, uint32_t type, uint32_t count)
{ m1136_u32(j, type); m1136_u32(j, count); }
void m1136_item(m1136_job *j, uint32_t type, uint32_t value)
{ m1136_record(j, type, 4); m1136_u32(j, value); }

static m1136_result begin(m1136_job *j, m1136_write_fn write,
                            void *context, const char *stamp, int manual)
{
    if (!j || !write || !stamp || strlen(stamp) != 14)
        return M1136_INVALID;
    for (unsigned i = 0; i < 14; ++i)
        if (stamp[i] < '0' || stamp[i] > '9') return M1136_INVALID;
    *j = (m1136_job){write, context, 0, 1, M1136_OK};
    char pjl[512];
    int n = snprintf(pjl, sizeof pjl,
        "\033%%-12345X@PJL JOB\n"
        "@PJL SET JAMRECOVERY=OFF\n@PJL SET DENSITY=3\n"
        "@PJL SET ECONOMODE=OFF\n@PJL SET RET=MEDIUM\n"
        "@PJL INFO STATUS\n@PJL USTATUS DEVICE = ON\n"
        "@PJL USTATUS JOB = ON\n@PJL USTATUS PAGE = ON\n"
        "@PJL USTATUS TIMED = 30\n@PJL SET JOBATTR=\"JobAttr4=%s\"", stamp);
    if (n < 0 || (size_t)n >= sizeof pjl) return j->error = M1136_INVALID;
    m1136_bytes(j, pjl, (size_t)n + 1); /* protocol includes NUL */
    static const char magic[] = "\033%-12345X,XQX";
    m1136_bytes(j, magic, sizeof magic - 1);
    m1136_record(j, 1, 7);
    m1136_item(j, 0x80000000, 84);
    m1136_item(j, 0x10000005, 1);
    m1136_item(j, 0x10000001, 0);
    m1136_item(j, 0x10000002, manual ? 2 : 0);
    m1136_item(j, 0x10000000, 0);
    m1136_item(j, 0x10000003, 1);
    m1136_item(j, 0x80000001, 0xdeadbeef);
    return j->error;
}

m1136_result m1136_job_begin(m1136_job *j, m1136_write_fn w, void *c, const char *stamp)
{ return begin(j,w,c,stamp,0); }
m1136_result m1136_job_begin_manual(m1136_job *j, m1136_write_fn w, void *c, const char *stamp)
{ return begin(j,w,c,stamp,1); }

m1136_result m1136_page_header(m1136_job *j, const m1136_page *p,
                              unsigned paper, unsigned copies, int pause)
{
    if (!j || !j->active) return M1136_STATE;
    if (j->error) return j->error;
    if (j->pages >= M1136_MAX_PAGES) return j->error = M1136_STATE;
    if (copies < 1 || copies > 99 || pause < -1 || pause > 3 || !p || !p->width || p->width > M1136_MAX_WIDTH ||
        !p->height || p->height > M1136_MAX_HEIGHT ||
        p->stride != ((size_t)p->width + 127) / 128 * 16 ||
        (paper != 1 && paper != 9)) return j->error = M1136_INVALID;
    uint32_t padded = (p->width + 127u) & ~127u;
    m1136_record(j, 3, pause < 0 ? 15 : 16);
    m1136_item(j, 0x80000000, pause < 0 ? 180 : 192);
    m1136_item(j, 0x20000005, copies);
    m1136_item(j, 0x20000006, 7);
    m1136_item(j, 0x20000000, 1);
    m1136_item(j, 0x20000007, 1);
    m1136_item(j, 0x20000008, 600);
    m1136_item(j, 0x20000009, 600);
    m1136_item(j, 0x2000000d, padded);
    m1136_item(j, 0x2000000e, p->height);
    m1136_item(j, 0x2000000a, 1);
    m1136_item(j, 0x2000000f, p->width);
    m1136_item(j, 0x20000010, p->height);
    m1136_item(j, 0x20000011, 0);
    if (pause >= 0) m1136_item(j, 0x20000012, (unsigned)pause);
    m1136_item(j, 0x20000001, paper);
    m1136_item(j, 0x80000001, 0xdeadbeef);
    return j->error;
}

m1136_result m1136_job_page(m1136_job *j, const m1136_page *p, unsigned paper, unsigned copies)
{
    if (!p || !p->bits) return M1136_INVALID;
    m1136_result result=m1136_page_header(j,p,paper,copies,-1);
    if (result) return result;
    j->error = m1136_encode(j, p);
    return m1136_page_finish(j);
}

m1136_result m1136_page_finish(m1136_job *j)
{
    m1136_record(j, 4, 0);
    if (!j->error) ++j->pages;
    return j->error;
}

m1136_result m1136_job_end(m1136_job *j)
{
    if (!j || !j->active) return M1136_STATE;
    j->active = 0;
    if (j->error) return j->error;
    if (!j->pages) return j->error = M1136_STATE;
    m1136_record(j, 2, 0);
    static const char tail[] = "\033%-12345X@PJL EOJ\n\033%-12345X";
    m1136_bytes(j, tail, sizeof tail - 1);
    return j->error;
}
