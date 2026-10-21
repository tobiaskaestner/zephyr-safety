/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/ztest.h>
#include <fakes/fatal.h>

DEFINE_FAKE_VOID_FUNC(z_fatal_error, unsigned int, const struct arch_esf *);

static void fatal_fakes_reset(const struct ztest_unit_test *test, void *fixture)
{
	ARG_UNUSED(test);
	ARG_UNUSED(fixture);

	FATAL_FFF_FAKES_LIST(RESET_FAKE);
}

ZTEST_RULE(fatal_fakes_reset, fatal_fakes_reset, NULL);
