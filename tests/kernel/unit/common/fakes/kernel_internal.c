/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/ztest.h>
#include <kernel_internal.h>

DEFINE_FAKE_VALUE_FUNC(bool, z_handle_obj_poll_events, sys_dlist_t *, uint32_t);

static void kernel_internal_fakes_reset(const struct ztest_unit_test *test, void *fixture)
{
	ARG_UNUSED(test);
	ARG_UNUSED(fixture);

	KERNEL_INTERNAL_FFF_FAKES_LIST(RESET_FAKE);
}

ZTEST_RULE(kernel_internal_fakes_reset, kernel_internal_fakes_reset, NULL);
