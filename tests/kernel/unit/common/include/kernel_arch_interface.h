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
 *
 * With CONFIG_USE_SWITCH, the real kernel_internal.h defines
 * arch_thread_return_value_set() as an inline function (it writes
 * thread->swap_retval). Then this header does not declare the fake.
 */

#ifndef ZEPHYR_KERNEL_INCLUDE_ARCH_INTERFACE_H_
#define ZEPHYR_KERNEL_INCLUDE_ARCH_INTERFACE_H_

#include <stdbool.h>
#include <zephyr/fff.h>

#ifdef __cplusplus
extern "C" {
#endif

struct k_thread;

#ifdef CONFIG_USE_SWITCH
#define KERNEL_ARCH_INTERFACE_RETURN_VALUE_FAKE(FAKE)
#else
#define KERNEL_ARCH_INTERFACE_RETURN_VALUE_FAKE(FAKE) FAKE(arch_thread_return_value_set)
#endif

#define KERNEL_ARCH_INTERFACE_FFF_FAKES_LIST(FAKE)                                                 \
	FAKE(arch_is_in_isr)                                                                       \
	KERNEL_ARCH_INTERFACE_RETURN_VALUE_FAKE(FAKE)                                              \
	FAKE(arch_coprocessors_disable)

DECLARE_FAKE_VALUE_FUNC(bool, arch_is_in_isr);
#ifndef CONFIG_USE_SWITCH
DECLARE_FAKE_VOID_FUNC(arch_thread_return_value_set, struct k_thread *, unsigned int);
#endif
/* halt_thread() of kernel/sched.c calls it for each aborted thread. */
DECLARE_FAKE_VALUE_FUNC(int, arch_coprocessors_disable, struct k_thread *);

#ifdef __cplusplus
}
#endif

#endif /* ZEPHYR_KERNEL_INCLUDE_ARCH_INTERFACE_H_ */
