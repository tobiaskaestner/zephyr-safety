/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Shadow of kernel/include/kernel_arch_interface.h.
 *
 * The real header declares the private kernel-to-arch interface. It is
 * not on the include path of a unit test, so in this build each function
 * is a plain FFF fake.
 */

#ifndef ZEPHYR_KERNEL_INCLUDE_ARCH_INTERFACE_H_
#define ZEPHYR_KERNEL_INCLUDE_ARCH_INTERFACE_H_

#include <stdbool.h>
#include <zephyr/fff.h>

#ifdef __cplusplus
extern "C" {
#endif

struct k_thread;

#define KERNEL_ARCH_INTERFACE_FFF_FAKES_LIST(FAKE)                                                 \
	FAKE(arch_is_in_isr)                                                                       \
	FAKE(arch_thread_return_value_set)

DECLARE_FAKE_VALUE_FUNC(bool, arch_is_in_isr);
DECLARE_FAKE_VOID_FUNC(arch_thread_return_value_set, struct k_thread *, unsigned int);

#ifdef __cplusplus
}
#endif

#endif /* ZEPHYR_KERNEL_INCLUDE_ARCH_INTERFACE_H_ */
