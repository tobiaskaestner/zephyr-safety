/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Fakes of kernel/thread.c (fake group thread).
 *
 * - z_dummy_thread_init(): halt_thread() of kernel/sched.c calls it when an
 *   ISR aborts the thread that it interrupted. The fake records the call.
 *
 * Do not link this group in a unit test of kernel/thread.c.
 */

#ifndef KERNEL_UNIT_FAKES_THREAD_H_
#define KERNEL_UNIT_FAKES_THREAD_H_

#include <zephyr/kernel.h>
#include <zephyr/fff.h>

#ifdef __cplusplus
extern "C" {
#endif

#define THREAD_FFF_FAKES_LIST(FAKE) FAKE(z_dummy_thread_init)

DECLARE_FAKE_VOID_FUNC(z_dummy_thread_init, struct k_thread *);

#ifdef __cplusplus
}
#endif

#endif /* KERNEL_UNIT_FAKES_THREAD_H_ */
