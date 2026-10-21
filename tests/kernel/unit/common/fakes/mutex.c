/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/ztest.h>
#include <fakes/mutex.h>

DEFINE_FAKE_VALUE_FUNC(int, k_mutex_lock, struct k_mutex *, k_timeout_t);
DEFINE_FAKE_VALUE_FUNC(int, k_mutex_unlock, struct k_mutex *);

static void mutex_fakes_reset(const struct ztest_unit_test *test, void *fixture)
{
	ARG_UNUSED(test);
	ARG_UNUSED(fixture);

	MUTEX_FFF_FAKES_LIST(RESET_FAKE);
}

ZTEST_RULE(mutex_fakes_reset, mutex_fakes_reset, NULL);
