/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/ztest.h>
#include <zephyr/fff.h>

DEFINE_FFF_GLOBALS;

static void fff_history_reset(const struct ztest_unit_test *test, void *fixture)
{
	ARG_UNUSED(test);
	ARG_UNUSED(fixture);

	FFF_RESET_HISTORY();
}

ZTEST_RULE(fff_history_reset, fff_history_reset, NULL);
