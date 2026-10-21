/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Fakes of the object core functions (zephyr/kernel/obj_core.h).
 *
 * The real header declares these functions extern, so it needs no shadow.
 * Link the fake group obj_core only if CONFIG_OBJ_CORE is enabled.
 */

#ifndef KERNEL_UNIT_FAKES_OBJ_CORE_H_
#define KERNEL_UNIT_FAKES_OBJ_CORE_H_

#include <zephyr/kernel.h>
#include <zephyr/fff.h>

#ifdef __cplusplus
extern "C" {
#endif

#define OBJ_CORE_FFF_FAKES_LIST(FAKE)                                                              \
	FAKE(k_obj_core_init)                                                                      \
	FAKE(k_obj_core_link)                                                                      \
	FAKE(k_obj_core_init_and_link)                                                             \
	FAKE(k_obj_core_unlink)

DECLARE_FAKE_VOID_FUNC(k_obj_core_init, struct k_obj_core *, struct k_obj_type *);
DECLARE_FAKE_VOID_FUNC(k_obj_core_link, struct k_obj_core *);
DECLARE_FAKE_VOID_FUNC(k_obj_core_init_and_link, struct k_obj_core *, struct k_obj_type *);
DECLARE_FAKE_VOID_FUNC(k_obj_core_unlink, struct k_obj_core *);

#ifdef __cplusplus
}
#endif

#endif /* KERNEL_UNIT_FAKES_OBJ_CORE_H_ */
