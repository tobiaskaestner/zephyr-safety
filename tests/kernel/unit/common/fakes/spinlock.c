/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/ztest.h>
#include <fakes/spinlock.h>

DEFINE_FAKE_VALUE_FUNC(bool, z_spin_lock_valid, struct k_spinlock *);
DEFINE_FAKE_VALUE_FUNC(bool, z_spin_unlock_valid, struct k_spinlock *);
DEFINE_FAKE_VOID_FUNC(z_spin_lock_set_owner, struct k_spinlock *);
DEFINE_FAKE_VOID_FUNC(z_spin_lock_transfer_owner, struct k_spinlock *);
DEFINE_FAKE_VOID_FUNC(z_assert_can_swap, unsigned int, struct k_spinlock *);
DEFINE_FAKE_VOID_FUNC(z_spin_validate_reset, bool);

/* Data of kernel/spinlock_validate.c: halt_thread() compares an address with it. */
const uint8_t z_spinlock_abort_sentinel;

static void spinlock_fakes_reset(const struct ztest_unit_test *test, void *fixture)
{
	ARG_UNUSED(test);
	ARG_UNUSED(fixture);

	SPINLOCK_FFF_FAKES_LIST(RESET_FAKE);

	z_spin_lock_valid_fake.return_val = true;
	z_spin_unlock_valid_fake.return_val = true;
}

ZTEST_RULE(spinlock_fakes_reset, spinlock_fakes_reset, NULL);
