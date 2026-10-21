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

#define SCHEDULER_FFF_FAKES_LIST(FAKE)                                                             \
	FAKE(z_sched_waitq_walk)                                                                   \
	FAKE(z_sched_wake_thread_locked)

DECLARE_FAKE_VALUE_FUNC(int, z_sched_waitq_walk, _wait_q_t *, _waitq_walk_cb_t,
			_waitq_post_walk_cb_t, void *);
DECLARE_FAKE_VOID_FUNC(z_sched_wake_thread_locked, struct k_thread *);

#ifdef __cplusplus
}
#endif

#endif /* ZEPHYR_KERNEL_INCLUDE_SCHEDULER_H_ */
