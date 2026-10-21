/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Shadow of kernel/include/timeout_q.h.
 *
 * Only the timeout functions that a unit under test uses are here. Each
 * one is an FFF fake, also the functions that are static inline in the
 * real header. The fake group sched defines them.
 *
 * Exception: z_is_inactive_timeout() is REAL. It only reads the timeout
 * structure. The copies of the real header (one for each timeout backend,
 * and the macro without CONFIG_SYS_CLOCK_EXISTS) are between the markers
 * KERNEL_UNIT_REAL_COPY_BEGIN and KERNEL_UNIT_REAL_COPY_END, without a
 * change. The conditions around them are the same as in the real header.
 * The drift guard (common/check_real_copies.py) checks the copies, but not
 * the conditions.
 */

#ifndef ZEPHYR_KERNEL_INCLUDE_TIMEOUT_Q_H_
#define ZEPHYR_KERNEL_INCLUDE_TIMEOUT_Q_H_

#include <stdbool.h>
#include <zephyr/kernel_structs.h>
#include <zephyr/sys/dlist.h>
#include <zephyr/fff.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TIMEOUT_Q_FFF_FAKES_LIST(FAKE) FAKE(z_try_abort_thread_timeout)

DECLARE_FAKE_VALUE_FUNC(int, z_try_abort_thread_timeout, struct k_thread *);

#ifdef CONFIG_SYS_CLOCK_EXISTS
#if defined(CONFIG_TIMEOUT_BACKEND_MINHEAP)
/* clang-format off */
/* KERNEL_UNIT_REAL_COPY_BEGIN kernel/include/timeout_q.h */
static inline bool z_is_inactive_timeout(const struct _timeout *to)
{
	return to->heap_handle.idx == 0U;
}
/* KERNEL_UNIT_REAL_COPY_END */
/* clang-format on */
#else /* CONFIG_TIMEOUT_BACKEND_WHEEL, _DLIST or _BUCKET */
/* clang-format off */
/* KERNEL_UNIT_REAL_COPY_BEGIN kernel/include/timeout_q.h */
static inline bool z_is_inactive_timeout(const struct _timeout *to)
{
	return !sys_dnode_is_linked(&to->node);
}
/* KERNEL_UNIT_REAL_COPY_END */
/* clang-format on */
#endif
#else
/* clang-format off */
/* KERNEL_UNIT_REAL_COPY_BEGIN kernel/include/timeout_q.h */
#define z_is_inactive_timeout(to) 1
/* KERNEL_UNIT_REAL_COPY_END */
/* clang-format on */
#endif

#ifdef __cplusplus
}
#endif

#endif /* ZEPHYR_KERNEL_INCLUDE_TIMEOUT_Q_H_ */
