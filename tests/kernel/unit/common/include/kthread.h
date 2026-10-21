/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Shadow of kernel/include/kthread.h.
 *
 * Only the thread functions that a unit under test uses are here.
 *
 * The thread state predicates below are REAL: they are copies of the static
 * inline functions of kernel/include/kthread.h, without a change. They only
 * read the thread structure, so a fake would only repeat the test data. A
 * test sets the thread state, and the unit reads it as the real kernel does
 * (user decision of 2026-10-20 for the pure helpers). Each copy is between
 * the markers KERNEL_UNIT_REAL_COPY_BEGIN and KERNEL_UNIT_REAL_COPY_END.
 * The drift guard (common/check_real_copies.py, called by
 * cmake/kernel_unit.cmake) stops the build if a copy is not the same as the
 * text of the real header. clang-format is off for the copies: the real
 * header does not follow the format of the harness.
 */

#ifndef ZEPHYR_KERNEL_INCLUDE_THREAD_H_
#define ZEPHYR_KERNEL_INCLUDE_THREAD_H_

#include <stdbool.h>
#include <zephyr/kernel.h>
#include <kernel_internal.h>
#include <timeout_q.h>

#ifdef __cplusplus
extern "C" {
#endif

/* clang-format off */
/* KERNEL_UNIT_REAL_COPY_BEGIN kernel/include/kthread.h */
static inline bool z_is_thread_pending(const struct k_thread *thread)
{
	return (thread->base.thread_state & _THREAD_PENDING) != 0U;
}
/* KERNEL_UNIT_REAL_COPY_END */
/* clang-format on */

/* clang-format off */
/* KERNEL_UNIT_REAL_COPY_BEGIN kernel/include/kthread.h */
static inline bool z_is_thread_prevented_from_running(const struct k_thread *thread)
{
	uint8_t state = thread->base.thread_state;

	return (state & (_THREAD_PENDING | _THREAD_SLEEPING | _THREAD_DEAD |
			 _THREAD_DUMMY | _THREAD_SUSPENDED)) != 0U;
}
/* KERNEL_UNIT_REAL_COPY_END */
/* clang-format on */

/* clang-format off */
/* KERNEL_UNIT_REAL_COPY_BEGIN kernel/include/kthread.h */
static inline bool z_is_thread_ready(const struct k_thread *thread)
{
	return !z_is_thread_prevented_from_running(thread);
}
/* KERNEL_UNIT_REAL_COPY_END */
/* clang-format on */

#ifdef __cplusplus
}
#endif

#endif /* ZEPHYR_KERNEL_INCLUDE_THREAD_H_ */
