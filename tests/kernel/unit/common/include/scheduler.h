/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Shadow of kernel/include/scheduler.h.
 *
 * The functions that only the real scheduler.h declares are FFF fakes
 * here. The other scheduler functions are fakes in the shadow ksched.h.
 *
 * Two lists, because the functions are in two source files:
 *
 * - SCHEDULER_FFF_FAKES_LIST: the functions of kernel/sched.c. The fake
 *   group sched defines them.
 * - SCHEDULER_C_FFF_FAKES_LIST: the functions of kernel/scheduler.c. The
 *   fake group scheduler defines them. The application scheduler (the unit
 *   test of kernel/scheduler.c) links the group sched and not the group
 *   scheduler, so its declarations here are the prototypes of the real
 *   functions.
 */

#ifndef ZEPHYR_KERNEL_INCLUDE_SCHEDULER_H_
#define ZEPHYR_KERNEL_INCLUDE_SCHEDULER_H_

#include <zephyr/fff.h>
#include <wait_q.h>
#include <ksched.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef int (*_waitq_walk_cb_t)(struct k_thread *thread, void *data);

typedef void (*_waitq_post_walk_cb_t)(int status, void *data);

/* The functions of kernel/sched.c (fake group sched). */
#define SCHEDULER_FFF_FAKES_LIST(FAKE)                                                             \
	FAKE(z_sched_wake_thread_locked)                                                           \
	FAKE(z_sched_lock_reschedule)

DECLARE_FAKE_VOID_FUNC(z_sched_wake_thread_locked, struct k_thread *);
DECLARE_FAKE_VOID_FUNC(z_sched_lock_reschedule, k_spinlock_key_t);

/* The functions of kernel/scheduler.c (fake group scheduler). */
#define SCHEDULER_C_FFF_FAKES_LIST(FAKE)                                                           \
	FAKE(z_sched_waitq_walk)                                                                   \
	FAKE(z_sched_wait)

DECLARE_FAKE_VALUE_FUNC(int, z_sched_waitq_walk, _wait_q_t *, _waitq_walk_cb_t,
			_waitq_post_walk_cb_t, void *);
DECLARE_FAKE_VALUE_FUNC(int, z_sched_wait, struct k_spinlock *, k_spinlock_key_t, _wait_q_t *,
			k_timeout_t, void **);

/*
 * z_sched_init() of kernel/scheduler.c: only the init code of the kernel
 * calls it, so no group has a fake. The prototype is for the application
 * scheduler.
 */
void z_sched_init(void);

#ifdef __cplusplus
}
#endif

#endif /* ZEPHYR_KERNEL_INCLUDE_SCHEDULER_H_ */
