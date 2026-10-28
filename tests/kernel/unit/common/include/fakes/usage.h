/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Fakes of the statistics functions of the kernel object (kernel/usage.c).
 *
 * kernel/include/kernel_internal.h declares these functions. With
 * CONFIG_OBJ_CORE_STATS_SYSTEM, kernel/obj_core.c puts them into the
 * statistics descriptor of the kernel object type. Link the fake group usage
 * only if CONFIG_OBJ_CORE_STATS_SYSTEM is enabled, and include this header
 * before the unit under test.
 */

#ifndef KERNEL_UNIT_FAKES_USAGE_H_
#define KERNEL_UNIT_FAKES_USAGE_H_

#include <zephyr/kernel.h>
#include <zephyr/fff.h>

#ifdef __cplusplus
extern "C" {
#endif

#define USAGE_FFF_FAKES_LIST(FAKE)                                                                 \
	FAKE(z_kernel_stats_raw)                                                                   \
	FAKE(z_kernel_stats_query)

DECLARE_FAKE_VALUE_FUNC(int, z_kernel_stats_raw, struct k_obj_core *, void *);
DECLARE_FAKE_VALUE_FUNC(int, z_kernel_stats_query, struct k_obj_core *, void *);

#ifdef __cplusplus
}
#endif

#endif /* KERNEL_UNIT_FAKES_USAGE_H_ */
