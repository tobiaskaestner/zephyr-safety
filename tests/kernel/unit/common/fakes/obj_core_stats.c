/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/ztest.h>
#include <fakes/obj_core_stats.h>

DEFINE_FAKE_VALUE_FUNC(int, k_obj_core_stats_register, struct k_obj_core *, void *, size_t);
DEFINE_FAKE_VALUE_FUNC(int, k_obj_core_stats_deregister, struct k_obj_core *);

static void obj_core_stats_fakes_reset(const struct ztest_unit_test *test, void *fixture)
{
	ARG_UNUSED(test);
	ARG_UNUSED(fixture);

	OBJ_CORE_STATS_FFF_FAKES_LIST(RESET_FAKE);
}

ZTEST_RULE(obj_core_stats_fakes_reset, obj_core_stats_fakes_reset, NULL);
