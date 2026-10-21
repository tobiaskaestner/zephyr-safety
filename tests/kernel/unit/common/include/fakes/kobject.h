/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Fakes of the kernel object functions (zephyr/sys/kobject.h).
 *
 * Without CONFIG_USERSPACE these functions are static inline and empty in
 * the real header. With CONFIG_USERSPACE they are extern, and these fakes
 * replace them. Link the fake group kobject only if CONFIG_USERSPACE is
 * enabled.
 */

#ifndef KERNEL_UNIT_FAKES_KOBJECT_H_
#define KERNEL_UNIT_FAKES_KOBJECT_H_

#include <zephyr/kernel.h>
#include <zephyr/fff.h>

#ifdef __cplusplus
extern "C" {
#endif

#define KOBJECT_FFF_FAKES_LIST(FAKE) FAKE(k_object_init)

DECLARE_FAKE_VOID_FUNC(k_object_init, const void *);

#ifdef __cplusplus
}
#endif

#endif /* KERNEL_UNIT_FAKES_KOBJECT_H_ */
