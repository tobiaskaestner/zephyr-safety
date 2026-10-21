/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Fakes of the object core statistics functions (zephyr/kernel/obj_core.h).
 *
 * kernel/obj_core.c implements these functions with CONFIG_OBJ_CORE_STATS.
 * They are a separate group from the fake group obj_core, so that a unit
 * links them only in the configurations that use them. Link the fake group
 * obj_core_stats only if CONFIG_OBJ_CORE_STATS is enabled, together with
 * the group obj_core.
 */

#ifndef KERNEL_UNIT_FAKES_OBJ_CORE_STATS_H_
#define KERNEL_UNIT_FAKES_OBJ_CORE_STATS_H_

#include <zephyr/kernel.h>
#include <zephyr/fff.h>

#ifdef __cplusplus
extern "C" {
#endif

#define OBJ_CORE_STATS_FFF_FAKES_LIST(FAKE)                                                        \
	FAKE(k_obj_core_stats_register)                                                            \
	FAKE(k_obj_core_stats_deregister)

DECLARE_FAKE_VALUE_FUNC(int, k_obj_core_stats_register, struct k_obj_core *, void *, size_t);
DECLARE_FAKE_VALUE_FUNC(int, k_obj_core_stats_deregister, struct k_obj_core *);

#ifdef __cplusplus
}
#endif

#endif /* KERNEL_UNIT_FAKES_OBJ_CORE_STATS_H_ */
