/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Shadow of the arch header kernel_arch_func.h (for Cortex-M:
 * arch/arm/include/cortex_m/kernel_arch_func.h).
 *
 * A real port defines the context switch in this header as inline code:
 * arch_swap() without CONFIG_USE_SWITCH, arch_switch() with it. The
 * unit_testing architecture has no such header. Here each function is an FFF
 * fake of the fake group arch. kernel/sched.c and kernel/include/kswap.h
 * include this header.
 *
 * A plain fake does not switch. The model group platform
 * (kernel_unit_platform.h) gives the fakes the behavior of the module
 * Platform (safety/spec/tla/lib/Platform.tla) for Cortex-M.
 */

#ifndef KERNEL_UNIT_KERNEL_ARCH_FUNC_H_
#define KERNEL_UNIT_KERNEL_ARCH_FUNC_H_

#include <zephyr/fff.h>

#ifdef __cplusplus
extern "C" {
#endif

#define KERNEL_ARCH_FUNC_FFF_FAKES_LIST(FAKE)                                                      \
	FAKE(arch_swap)                                                                            \
	FAKE(arch_switch)                                                                          \
	FAKE(arch_spin_relax)

/*
 * Without CONFIG_USE_SWITCH: z_swap_irqlock() of kswap.h calls it with the key
 * of the critical section. On Cortex-M it sets PendSV pending, unlocks the
 * interrupts and returns the swap return value after the switch back.
 */
DECLARE_FAKE_VALUE_FUNC(int, arch_swap, unsigned int);

/*
 * With CONFIG_USE_SWITCH: do_swap() of kswap.h calls it after it has set
 * _current to the new thread. The arch code stores the handle of the old
 * thread in *switched_from.
 */
DECLARE_FAKE_VOID_FUNC(arch_switch, void *, void **);

/* zephyr/arch/arch_interface.h declares it. The SMP code of sched.c calls it. */
DECLARE_FAKE_VOID_FUNC(arch_spin_relax);

#ifdef __cplusplus
}
#endif

#endif /* KERNEL_UNIT_KERNEL_ARCH_FUNC_H_ */
