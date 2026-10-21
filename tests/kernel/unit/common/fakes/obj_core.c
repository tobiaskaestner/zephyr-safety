/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/ztest.h>
#include <fakes/obj_core.h>

DEFINE_FAKE_VOID_FUNC(k_obj_core_init, struct k_obj_core *, struct k_obj_type *);
DEFINE_FAKE_VOID_FUNC(k_obj_core_link, struct k_obj_core *);
DEFINE_FAKE_VOID_FUNC(k_obj_core_init_and_link, struct k_obj_core *, struct k_obj_type *);
DEFINE_FAKE_VOID_FUNC(k_obj_core_unlink, struct k_obj_core *);

static void obj_core_fakes_reset(const struct ztest_unit_test *test, void *fixture)
{
	ARG_UNUSED(test);
	ARG_UNUSED(fixture);

	OBJ_CORE_FFF_FAKES_LIST(RESET_FAKE);
}

ZTEST_RULE(obj_core_fakes_reset, obj_core_fakes_reset, NULL);
