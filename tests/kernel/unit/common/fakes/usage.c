/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/ztest.h>
#include <fakes/usage.h>

DEFINE_FAKE_VALUE_FUNC(int, z_kernel_stats_raw, struct k_obj_core *, void *);
DEFINE_FAKE_VALUE_FUNC(int, z_kernel_stats_query, struct k_obj_core *, void *);

static void usage_fakes_reset(const struct ztest_unit_test *test, void *fixture)
{
	ARG_UNUSED(test);
	ARG_UNUSED(fixture);

	USAGE_FFF_FAKES_LIST(RESET_FAKE);
}

ZTEST_RULE(usage_fakes_reset, usage_fakes_reset, NULL);
