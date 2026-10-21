/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/ztest.h>
#include <fakes/log_minimal.h>

DEFINE_FAKE_VOID_FUNC_VARARG(z_log_minimal_printk, const char *, ...);

static void log_minimal_fakes_reset(const struct ztest_unit_test *test, void *fixture)
{
	ARG_UNUSED(test);
	ARG_UNUSED(fixture);

	LOG_MINIMAL_FFF_FAKES_LIST(RESET_FAKE);
}

ZTEST_RULE(log_minimal_fakes_reset, log_minimal_fakes_reset, NULL);
