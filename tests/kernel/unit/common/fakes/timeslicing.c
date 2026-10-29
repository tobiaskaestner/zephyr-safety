/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/* Fakes of kernel/timeslicing.c (fake group timeslicing). See fakes/timeslicing.h. */

#include <zephyr/ztest.h>
#include <fakes/timeslicing.h>

DEFINE_FAKE_VOID_FUNC(z_time_slice_reset, struct k_thread *);

struct k_thread *pending_current;

static void timeslicing_fakes_reset(const struct ztest_unit_test *test, void *fixture)
{
	ARG_UNUSED(test);
	ARG_UNUSED(fixture);

	TIMESLICING_FFF_FAKES_LIST(RESET_FAKE);
	pending_current = NULL;
}

ZTEST_RULE(timeslicing_fakes_reset, timeslicing_fakes_reset, NULL);
