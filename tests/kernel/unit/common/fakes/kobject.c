/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/ztest.h>
#include <fakes/kobject.h>

DEFINE_FAKE_VOID_FUNC(k_object_init, const void *);

static void kobject_fakes_reset(const struct ztest_unit_test *test, void *fixture)
{
	ARG_UNUSED(test);
	ARG_UNUSED(fixture);

	KOBJECT_FFF_FAKES_LIST(RESET_FAKE);
}

ZTEST_RULE(kobject_fakes_reset, kobject_fakes_reset, NULL);
