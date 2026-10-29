/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/* Fakes of kernel/thread.c (fake group thread). See fakes/thread.h. */

#include <zephyr/ztest.h>
#include <fakes/thread.h>

DEFINE_FAKE_VOID_FUNC(z_dummy_thread_init, struct k_thread *);

static void thread_fakes_reset(const struct ztest_unit_test *test, void *fixture)
{
	ARG_UNUSED(test);
	ARG_UNUSED(fixture);

	THREAD_FFF_FAKES_LIST(RESET_FAKE);
}

ZTEST_RULE(thread_fakes_reset, thread_fakes_reset, NULL);
