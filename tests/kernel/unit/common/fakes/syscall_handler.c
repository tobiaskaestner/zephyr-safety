/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/ztest.h>
#include <zephyr/internal/syscall_handler.h>

DEFINE_FAKE_VALUE_FUNC(struct k_object *, k_object_find, const void *);
DEFINE_FAKE_VALUE_FUNC(int, k_object_validation_check, struct k_object *, const void *,
		       enum k_objects, enum _obj_init_check);
DEFINE_FAKE_VOID_FUNC(unit_syscall_oops);

static void syscall_handler_fakes_reset(const struct ztest_unit_test *test, void *fixture)
{
	ARG_UNUSED(test);
	ARG_UNUSED(fixture);

	SYSCALL_HANDLER_FFF_FAKES_LIST(RESET_FAKE);
}

ZTEST_RULE(syscall_handler_fakes_reset, syscall_handler_fakes_reset, NULL);

DEFINE_FAKE_VALUE_FUNC(int, arch_buffer_validate, const void *, size_t, int);

static void syscall_handler_memory_fakes_reset(const struct ztest_unit_test *test, void *fixture)
{
	ARG_UNUSED(test);
	ARG_UNUSED(fixture);

	SYSCALL_HANDLER_MEMORY_FFF_FAKES_LIST(RESET_FAKE);
}

ZTEST_RULE(syscall_handler_memory_fakes_reset, syscall_handler_memory_fakes_reset, NULL);
