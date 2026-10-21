/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/ztest.h>
#include <fakes/mempool.h>

DEFINE_FAKE_VALUE_FUNC(void *, z_thread_malloc, size_t);
DEFINE_FAKE_VOID_FUNC(k_free, void *);

static void mempool_fakes_reset(const struct ztest_unit_test *test, void *fixture)
{
	ARG_UNUSED(test);
	ARG_UNUSED(fixture);

	MEMPOOL_FFF_FAKES_LIST(RESET_FAKE);
}

ZTEST_RULE(mempool_fakes_reset, mempool_fakes_reset, NULL);
