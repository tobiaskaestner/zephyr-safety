/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/ztest.h>
#include <fakes/assert.h>

DEFINE_FAKE_VOID_FUNC_VARARG(assert_print, const char *, ...);
#ifdef CONFIG_ASSERT_NO_FILE_INFO
DEFINE_FAKE_VOID_FUNC(assert_post_action);
#else
DEFINE_FAKE_VOID_FUNC(assert_post_action, const char *, unsigned int);
#endif

static void assert_fakes_reset(const struct ztest_unit_test *test, void *fixture)
{
	ARG_UNUSED(test);
	ARG_UNUSED(fixture);

	ASSERT_FFF_FAKES_LIST(RESET_FAKE);
}

ZTEST_RULE(assert_fakes_reset, assert_fakes_reset, NULL);
