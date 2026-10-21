/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Fakes of the mutex system calls of kernel/mutex.c.
 *
 * zephyr/kernel.h declares k_mutex_lock() and k_mutex_unlock() as system
 * calls (__syscall). The unittest build does not generate
 * zephyr/syscalls/kernel.h, and __syscall is empty for ZTEST_UNITTEST.
 * Thus a unit that calls these functions calls extern functions, and these
 * fakes replace them.
 *
 * After the reset of each test, both fakes return 0. A test that models a
 * mutex sets custom_fake. Link the fake group mutex only if the unit under
 * test is not kernel/mutex.c.
 */

#ifndef KERNEL_UNIT_FAKES_MUTEX_H_
#define KERNEL_UNIT_FAKES_MUTEX_H_

#include <zephyr/kernel.h>
#include <zephyr/fff.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MUTEX_FFF_FAKES_LIST(FAKE)                                                                 \
	FAKE(k_mutex_lock)                                                                         \
	FAKE(k_mutex_unlock)

DECLARE_FAKE_VALUE_FUNC(int, k_mutex_lock, struct k_mutex *, k_timeout_t);
DECLARE_FAKE_VALUE_FUNC(int, k_mutex_unlock, struct k_mutex *);

#ifdef __cplusplus
}
#endif

#endif /* KERNEL_UNIT_FAKES_MUTEX_H_ */
