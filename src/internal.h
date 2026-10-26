/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef M1136_INTERNAL_H
#define M1136_INTERNAL_H
#include "m1136.h"
void m1136_bytes(m1136_job *, const void *, size_t);
void m1136_u32(m1136_job *, uint32_t);
void m1136_record(m1136_job *, uint32_t, uint32_t);
void m1136_item(m1136_job *, uint32_t, uint32_t);
m1136_result m1136_encode(m1136_job *, const m1136_page *);
/* Header/finish also frame trusted, locally encoded duplex spool data. */
m1136_result m1136_page_header(m1136_job *, const m1136_page *, unsigned, unsigned, int);
m1136_result m1136_page_finish(m1136_job *);
m1136_result m1136_job_begin_manual(m1136_job *, m1136_write_fn, void *, const char *);
#endif
