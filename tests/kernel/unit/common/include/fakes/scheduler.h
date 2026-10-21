/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Fakes of the scheduler system calls of kernel/scheduler.c.
 *
 * - k_sched_current_thread_query(): zephyr/kernel.h declares it as a
 *   system call (__syscall). The unittest build does not generate
 *   zephyr/syscalls/kernel.h, and __syscall is empty for ZTEST_UNITTEST.
 *   Thus the unit calls an extern function, and this fake replaces it.
 *   k_current_get() in zephyr/kernel.h also calls it.
 *
 * After the reset of each test, k_sched_current_thread_query() returns
 * NULL. A test that needs a current thread sets return_val. Link the fake
 * group scheduler only if the unit under test is not kernel/scheduler.c.
 */

#ifndef KERNEL_UNIT_FAKES_SCHEDULER_H_
#define KERNEL_UNIT_FAKES_SCHEDULER_H_

#include <zephyr/kernel.h>
#include <zephyr/fff.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SCHEDULER_SYSCALL_FFF_FAKES_LIST(FAKE) FAKE(k_sched_current_thread_query)

DECLARE_FAKE_VALUE_FUNC(k_tid_t, k_sched_current_thread_query);

#ifdef __cplusplus
}
#endif

#endif /* KERNEL_UNIT_FAKES_SCHEDULER_H_ */
