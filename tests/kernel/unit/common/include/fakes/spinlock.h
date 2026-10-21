/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Fakes of the spinlock validation functions (zephyr/spinlock.h).
 *
 * The unit tests use the real spinlock.h: k_spin_lock() and
 * k_spin_unlock() are inline and call the arch layer fakes. With
 * CONFIG_SPIN_VALIDATE they also call these functions. After the reset
 * of each test, z_spin_lock_valid() and z_spin_unlock_valid() return
 * true. Link the fake group spinlock only if CONFIG_SPIN_VALIDATE is
 * enabled.
 */

#ifndef KERNEL_UNIT_FAKES_SPINLOCK_H_
#define KERNEL_UNIT_FAKES_SPINLOCK_H_

#include <stdbool.h>
#include <zephyr/spinlock.h>
#include <zephyr/fff.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SPINLOCK_FFF_FAKES_LIST(FAKE)                                                              \
	FAKE(z_spin_lock_valid)                                                                    \
	FAKE(z_spin_unlock_valid)                                                                  \
	FAKE(z_spin_lock_set_owner)                                                                \
	FAKE(z_spin_lock_transfer_owner)

DECLARE_FAKE_VALUE_FUNC(bool, z_spin_lock_valid, struct k_spinlock *);
DECLARE_FAKE_VALUE_FUNC(bool, z_spin_unlock_valid, struct k_spinlock *);
DECLARE_FAKE_VOID_FUNC(z_spin_lock_set_owner, struct k_spinlock *);
DECLARE_FAKE_VOID_FUNC(z_spin_lock_transfer_owner, struct k_spinlock *);

#ifdef __cplusplus
}
#endif

#endif /* KERNEL_UNIT_FAKES_SPINLOCK_H_ */
