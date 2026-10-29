/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * The fakes of kernel/scheduler.c (fake group scheduler): the system call
 * k_sched_current_thread_query() (fakes/scheduler.h) and the kernel-internal
 * functions z_sched_waitq_walk() and z_sched_wait() (shadow scheduler.h).
 * The application scheduler, the unit test of kernel/scheduler.c, does not
 * link this group.
 */

#include <zephyr/ztest.h>
#include <scheduler.h>
#include <fakes/scheduler.h>

DEFINE_FAKE_VALUE_FUNC(k_tid_t, k_sched_current_thread_query);
DEFINE_FAKE_VALUE_FUNC(int, z_sched_waitq_walk, _wait_q_t *, _waitq_walk_cb_t,
		       _waitq_post_walk_cb_t, void *);
DEFINE_FAKE_VALUE_FUNC(int, z_sched_wait, struct k_spinlock *, k_spinlock_key_t, _wait_q_t *,
		       k_timeout_t, void **);

static void scheduler_fakes_reset(const struct ztest_unit_test *test, void *fixture)
{
	ARG_UNUSED(test);
	ARG_UNUSED(fixture);

	SCHEDULER_SYSCALL_FFF_FAKES_LIST(RESET_FAKE);
	SCHEDULER_C_FFF_FAKES_LIST(RESET_FAKE);
}

ZTEST_RULE(scheduler_fakes_reset, scheduler_fakes_reset, NULL);
